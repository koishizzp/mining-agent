import csv
import json
from pathlib import Path

from . import __version__
from .control_plane.stage_graph import build_stage_order
from .io_utils import read_fasta, sha256_file
from .reporting import write_report_outputs
from .settings import load_settings
from .stage_layout import build_stage_dirs
from .steps.foldseek_client import run_foldseek_stage
from .steps.mmseqs_cluster import run_mmseqs_cluster
from .steps.prefilter import run_prefilter
from .steps.protrek_bridge import run_protrek_stage
from .steps.rerank import combine_stage_scores
from .steps.structure_predict import run_structure_predict_stage
from .steps.temstapro_screen import run_temstapro_screen


def should_skip_stage(done_path: str | Path, expected_input_hash: str, resume: bool) -> bool:
    if not resume:
        return False
    done_path = Path(done_path)
    if not done_path.exists():
        return False
    payload = json.loads(done_path.read_text(encoding="utf-8"))
    return payload.get("input_hash") == expected_input_hash


def _read_scores_tsv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def run_pipeline(
    config_path: str | Path,
    run_name: str,
    input_faa: str | Path,
    resume: bool = False,
) -> dict[str, Path]:
    settings = load_settings(config_path)
    stage_order = build_stage_order("proteins")
    run_root = Path(settings.runtime.runs_root) / run_name
    stage_dirs = build_stage_dirs(run_root, stage_order)
    input_faa = Path(input_faa)

    prefilter_done = stage_dirs["prefilter"] / "DONE.json"
    if should_skip_stage(prefilter_done, sha256_file(input_faa), resume):
        prefilter_result = {"filtered_faa": stage_dirs["prefilter"] / "filtered.faa"}
    else:
        prefilter_result = run_prefilter(
            input_faa=input_faa,
            stage_dir=stage_dirs["prefilter"],
            min_length=settings.defaults.prefilter_min_length,
            max_length=settings.defaults.prefilter_max_length,
            max_single_residue_fraction=settings.defaults.prefilter_max_single_residue_fraction,
            software_version=__version__,
        )

    cluster_input = Path(prefilter_result["filtered_faa"])
    cluster_done = stage_dirs["mmseqs_cluster"] / "DONE.json"
    if should_skip_stage(cluster_done, sha256_file(cluster_input), resume):
        cluster_result = {
            "cluster_rep_faa": stage_dirs["mmseqs_cluster"] / "cluster_rep_seq.fasta",
            "cluster_membership_tsv": stage_dirs["mmseqs_cluster"] / "cluster_cluster.tsv",
        }
    else:
        cluster_result = run_mmseqs_cluster(
            input_faa=cluster_input,
            stage_dir=stage_dirs["mmseqs_cluster"],
            mmseqs_bin=settings.tools.mmseqs_bin,
            min_seq_id=settings.defaults.cluster_min_seq_id,
            coverage=settings.defaults.cluster_coverage,
            threads=settings.defaults.cluster_threads,
            software_version=__version__,
        )

    thermo_input = Path(cluster_result["cluster_rep_faa"])
    thermo_done = stage_dirs["temstapro_screen"] / "DONE.json"
    if should_skip_stage(thermo_done, sha256_file(thermo_input), resume):
        thermo_result = {
            "thermo_hits_faa": stage_dirs["temstapro_screen"] / "thermo_hits.faa",
            "thermo_scores_tsv": stage_dirs["temstapro_screen"] / "scores.tsv",
        }
    else:
        thermo_result = run_temstapro_screen(
            input_faa=thermo_input,
            stage_dir=stage_dirs["temstapro_screen"],
            conda_bin=settings.tools.conda_bin,
            conda_env_name=settings.tools.temstapro_conda_env_name,
            temstapro_bin=settings.tools.temstapro_bin,
            repo_root=settings.tools.temstapro_repo_root,
            model_dir=settings.tools.temstapro_model_dir,
            cache_dir=settings.tools.temstapro_cache_dir,
            hf_home=settings.tools.temstapro_hf_home,
            transformers_offline=settings.tools.temstapro_transformers_offline,
            top_fraction=settings.defaults.thermo_top_fraction,
            min_score=settings.defaults.thermo_min_score,
            software_version=__version__,
        )

    protrek_input = Path(thermo_result["thermo_hits_faa"])
    protrek_done = stage_dirs["protrek_recall"] / "DONE.json"
    if should_skip_stage(protrek_done, sha256_file(protrek_input), resume):
        protrek_result = {"protrek_scores_tsv": stage_dirs["protrek_recall"] / "scores.tsv"}
    else:
        protrek_result = run_protrek_stage(
            input_faa=protrek_input,
            stage_dir=stage_dirs["protrek_recall"],
            python_bin=settings.tools.protrek_python_bin,
            index_script="scripts/protrek_build_index.py",
            query_script="scripts/protrek_query.py",
            repo_root=settings.tools.protrek_repo_root,
            weights_dir=settings.tools.protrek_weights_dir,
            query_texts=list(settings.defaults.protrek_query_texts),
            batch_size=settings.defaults.protrek_batch_size,
            top_k=settings.defaults.protrek_top_k,
            software_version=__version__,
        )

    structure_done = stage_dirs["structure_predict"] / "DONE.json"
    structure_manifest_path = stage_dirs["structure_predict"] / "structure_manifest.json"
    if should_skip_stage(structure_done, sha256_file(protrek_input), resume) and structure_manifest_path.exists():
        structure_result = {
            "structure_manifest": json.loads(structure_manifest_path.read_text(encoding="utf-8")),
            "structure_manifest_json": structure_manifest_path,
        }
    else:
        structure_result = run_structure_predict_stage(
            input_faa=protrek_input,
            stage_dir=stage_dirs["structure_predict"],
            colabfold_batch_bin=settings.tools.colabfold_batch_bin,
            colabfold_data_dir=settings.tools.colabfold_data_dir,
            msa_mode=settings.defaults.colabfold_msa_mode,
            num_models=settings.defaults.colabfold_num_models,
            num_recycle=settings.defaults.colabfold_num_recycle,
            software_version=__version__,
        )

    foldseek_result = run_foldseek_stage(
        structure_manifest=list(structure_result["structure_manifest"]),
        stage_dir=stage_dirs["foldseek_confirm"],
        foldseek_bin=settings.tools.foldseek_bin,
        database_path=settings.tools.foldseek_database_path,
        topk=settings.defaults.foldseek_topk,
        min_tmscore=settings.defaults.foldseek_min_tmscore,
        software_version=__version__,
    )

    combined_rows = combine_stage_scores(
        thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
        protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
        foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
        hot_spring_ids={record.protein_id for record in read_fasta(input_faa)},
    )
    return write_report_outputs(stage_dirs["rerank_report"], run_name, combined_rows)
