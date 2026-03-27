import csv
import json
from pathlib import Path

from . import __version__
from .config import load_pipeline_config, stage_output_dirs
from .io_utils import read_fasta, sha256_file
from .reporting import write_report_outputs
from .steps.foldseek_client import run_foldseek_stage
from .steps.mmseqs_cluster import run_mmseqs_cluster
from .steps.prefilter import run_prefilter
from .steps.protrek_bridge import run_protrek_stage
from .steps.rerank import combine_stage_scores
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


def _foldseek_manifest(input_faa: str | Path, stage_dir: str | Path) -> list[dict[str, str]]:
    structures_dir = Path(stage_dir) / "structures"
    return [
        {
            "protein_id": record.protein_id,
            "pdb_path": str(structures_dir / f"{record.protein_id}.pdb"),
        }
        for record in read_fasta(input_faa)
    ]


def run_pipeline(
    config_path: str | Path,
    run_name: str,
    input_faa: str | Path,
    resume: bool = False,
) -> dict[str, Path]:
    cfg = load_pipeline_config(config_path)
    stage_dirs = stage_output_dirs(cfg.results_root, run_name)
    input_faa = Path(input_faa)

    prefilter_done = stage_dirs["01_prefilter"] / "DONE.json"
    if should_skip_stage(prefilter_done, sha256_file(input_faa), resume):
        prefilter_result = {"filtered_faa": stage_dirs["01_prefilter"] / "filtered.faa"}
    else:
        prefilter_result = run_prefilter(
            input_faa=input_faa,
            stage_dir=stage_dirs["01_prefilter"],
            min_length=cfg.prefilter.min_length,
            max_length=cfg.prefilter.max_length,
            max_single_residue_fraction=cfg.prefilter.max_single_residue_fraction,
            software_version=__version__,
        )

    cluster_input = Path(prefilter_result["filtered_faa"])
    cluster_done = stage_dirs["02_cluster"] / "DONE.json"
    if should_skip_stage(cluster_done, sha256_file(cluster_input), resume):
        cluster_result = {
            "cluster_rep_faa": stage_dirs["02_cluster"] / "cluster_rep_seq.fasta",
            "cluster_membership_tsv": stage_dirs["02_cluster"] / "cluster_cluster.tsv",
        }
    else:
        cluster_result = run_mmseqs_cluster(
            input_faa=cluster_input,
            stage_dir=stage_dirs["02_cluster"],
            mmseqs_bin=cfg.cluster.mmseqs_bin,
            min_seq_id=cfg.cluster.min_seq_id,
            coverage=cfg.cluster.coverage,
            threads=cfg.cluster.threads,
            software_version=__version__,
        )

    thermo_input = Path(cluster_result["cluster_rep_faa"])
    thermo_done = stage_dirs["03_thermo_screen"] / "DONE.json"
    if should_skip_stage(thermo_done, sha256_file(thermo_input), resume):
        thermo_result = {
            "thermo_hits_faa": stage_dirs["03_thermo_screen"] / "thermo_hits.faa",
            "thermo_scores_tsv": stage_dirs["03_thermo_screen"] / "scores.tsv",
        }
    else:
        thermo_result = run_temstapro_screen(
            input_faa=thermo_input,
            stage_dir=stage_dirs["03_thermo_screen"],
            temstapro_bin=cfg.thermo.temstapro_bin,
            model_dir=cfg.thermo.model_dir,
            cache_dir=cfg.thermo.cache_dir,
            top_fraction=cfg.thermo.top_fraction,
            min_score=cfg.thermo.min_score,
            software_version=__version__,
        )

    protrek_input = Path(thermo_result["thermo_hits_faa"])
    protrek_done = stage_dirs["04_protrek_recall"] / "DONE.json"
    if should_skip_stage(protrek_done, sha256_file(protrek_input), resume):
        protrek_result = {"protrek_scores_tsv": stage_dirs["04_protrek_recall"] / "scores.tsv"}
    else:
        protrek_result = run_protrek_stage(
            input_faa=protrek_input,
            stage_dir=stage_dirs["04_protrek_recall"],
            python_bin=cfg.protrek.python_bin,
            index_script=cfg.protrek.index_script,
            query_script=cfg.protrek.query_script,
            repo_root=cfg.protrek.repo_root,
            weights_dir=cfg.protrek.weights_dir,
            query_texts=list(cfg.protrek.query_texts),
            batch_size=cfg.protrek.batch_size,
            top_k=cfg.protrek.top_k,
            software_version=__version__,
        )

    foldseek_result = run_foldseek_stage(
        structure_manifest=_foldseek_manifest(protrek_input, stage_dirs["05_foldseek_confirm"]),
        stage_dir=stage_dirs["05_foldseek_confirm"],
        base_url=cfg.foldseek.base_url,
        database=cfg.foldseek.database,
        topk=cfg.foldseek.topk,
        min_tmscore=cfg.foldseek.min_tmscore,
        software_version=__version__,
    )

    combined_rows = combine_stage_scores(
        thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
        protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
        foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
        hot_spring_ids={record.protein_id for record in read_fasta(input_faa)},
    )
    return write_report_outputs(stage_dirs["06_rerank"], run_name, combined_rows)
