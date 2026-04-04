import json
import os
from datetime import UTC, datetime
from pathlib import Path

from thermo_mining import __version__
from thermo_mining.control_plane.run_store import write_runtime_state
from thermo_mining.control_plane.upstream_steps import run_fastp_stage, run_prodigal_stage, run_spades_stage
from thermo_mining.io_utils import read_fasta
from thermo_mining.pipeline import _read_scores_tsv
from thermo_mining.reporting import write_report_outputs
from thermo_mining.settings import PlatformSettings, load_settings
from thermo_mining.stage_layout import build_stage_dirs
from thermo_mining.steps.foldseek_client import run_foldseek_stage
from thermo_mining.steps.mmseqs_cluster import run_mmseqs_cluster
from thermo_mining.steps.prefilter import run_prefilter
from thermo_mining.steps.protrek_bridge import run_protrek_stage
from thermo_mining.steps.rerank import combine_stage_scores
from thermo_mining.steps.seed_recall_merge import run_seed_recall_merge_stage
from thermo_mining.steps.seed_sequence_recall import run_seed_sequence_recall_stage
from thermo_mining.steps.seed_structure_recall import run_seed_structure_recall_stage
from thermo_mining.steps.structure_predict import run_structure_predict_stage
from thermo_mining.steps.temstapro_screen import run_temstapro_screen


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_plan(run_dir: Path) -> dict[str, object]:
    return json.loads((run_dir / "execution_plan.json").read_text(encoding="utf-8"))


def _default_platform_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "platform.example.yaml"


def _load_platform_settings() -> PlatformSettings:
    config_path = Path(os.getenv("THERMO_PLATFORM_CONFIG", str(_default_platform_config_path())))
    return load_settings(config_path)


def _write_stage_state(
    run_dir: Path,
    status: str,
    active_stage: str | None,
    error_summary: str | None = None,
) -> None:
    existing = json.loads((run_dir / "runtime_state.json").read_text(encoding="utf-8"))
    existing["status"] = status
    existing["active_stage"] = active_stage
    existing["error_summary"] = error_summary
    existing["updated_at"] = _now_iso()
    write_runtime_state(run_dir, existing)


def _plan_override(plan: dict[str, object], key: str, default: object) -> object:
    overrides = plan.get("parameter_overrides") or {}
    if not isinstance(overrides, dict):
        return default
    return overrides.get(key, default)


def run_job(run_dir: str | Path) -> None:
    run_dir = Path(run_dir)
    plan = _load_plan(run_dir)
    settings = _load_platform_settings()
    bundle = plan["input_items"][0]
    stage_order = list(plan["stage_order"])
    stage_dirs = build_stage_dirs(run_dir, stage_order)
    current_input = Path(bundle["input_paths"][0])
    seed_input = Path(bundle["seed_paths"][0]) if bundle["bundle_type"] == "seeded_proteins" else None
    cleaned_reads: dict[str, Path] | None = None
    sequence_result: dict[str, Path] | None = None
    structure_recall_result: dict[str, Path] | None = None
    seeded_merge_rows: list[dict[str, object]] = []
    skip_downstream_for_empty_seeded_run = False
    thermo_result: dict[str, Path] | None = None
    protrek_result: dict[str, Path] | None = None
    structure_result: dict[str, object] | None = None
    foldseek_result: dict[str, Path] | None = None
    active_stage: str | None = None

    _write_stage_state(run_dir, "running", None, None)

    try:
        for stage_name in stage_order:
            active_stage = stage_name
            _write_stage_state(run_dir, "running", active_stage, None)

            if stage_name == "fastp":
                cleaned_reads = run_fastp_stage(
                    read1=bundle["input_paths"][0],
                    read2=bundle["input_paths"][1],
                    stage_dir=stage_dirs[stage_name],
                    fastp_bin=settings.tools.fastp_bin,
                )
            elif stage_name == "spades":
                if cleaned_reads is None:
                    raise RuntimeError("spades stage requires fastp outputs")
                spades_result = run_spades_stage(
                    read1=cleaned_reads["read1"],
                    read2=cleaned_reads["read2"],
                    stage_dir=stage_dirs[stage_name],
                    spades_bin=settings.tools.spades_bin,
                    threads=32,
                )
                current_input = Path(spades_result["contigs_fa"])
            elif stage_name == "prodigal":
                prodigal_result = run_prodigal_stage(
                    contigs_fa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    prodigal_bin=settings.tools.prodigal_bin,
                    software_version=__version__,
                )
                current_input = Path(prodigal_result["proteins_faa"])
            elif stage_name == "prefilter":
                prefilter_result = run_prefilter(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    min_length=int(_plan_override(plan, "prefilter_min_length", settings.defaults.prefilter_min_length)),
                    max_length=int(_plan_override(plan, "prefilter_max_length", settings.defaults.prefilter_max_length)),
                    max_single_residue_fraction=float(
                        _plan_override(
                            plan,
                            "prefilter_max_single_residue_fraction",
                            settings.defaults.prefilter_max_single_residue_fraction,
                        )
                    ),
                    software_version=__version__,
                )
                current_input = Path(prefilter_result["filtered_faa"])
            elif stage_name == "mmseqs_cluster":
                cluster_result = run_mmseqs_cluster(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    mmseqs_bin=settings.tools.mmseqs_bin,
                    min_seq_id=float(_plan_override(plan, "cluster_min_seq_id", settings.defaults.cluster_min_seq_id)),
                    coverage=float(_plan_override(plan, "cluster_coverage", settings.defaults.cluster_coverage)),
                    threads=int(_plan_override(plan, "cluster_threads", settings.defaults.cluster_threads)),
                    software_version=__version__,
                )
                current_input = Path(cluster_result["cluster_rep_faa"])
            elif stage_name == "seed_sequence_recall":
                if seed_input is None:
                    raise RuntimeError("seed_sequence_recall stage requires a seed input")
                sequence_result = run_seed_sequence_recall_stage(
                    seed_faa=seed_input,
                    target_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    mmseqs_bin=settings.tools.mmseqs_bin,
                    min_seq_id=float(
                        _plan_override(plan, "seed_sequence_min_seq_id", settings.defaults.seed_sequence_min_seq_id)
                    ),
                    coverage=float(
                        _plan_override(plan, "seed_sequence_coverage", settings.defaults.seed_sequence_coverage)
                    ),
                    topk_per_seed=int(
                        _plan_override(
                            plan,
                            "seed_sequence_topk_per_seed",
                            settings.defaults.seed_sequence_topk_per_seed,
                        )
                    ),
                    threads=int(_plan_override(plan, "cluster_threads", settings.defaults.cluster_threads)),
                    software_version=__version__,
                )
            elif stage_name == "seed_structure_recall":
                if seed_input is None:
                    raise RuntimeError("seed_structure_recall stage requires a seed input")
                structure_recall_result = run_seed_structure_recall_stage(
                    seed_faa=seed_input,
                    cluster_rep_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    colabfold_batch_bin=settings.tools.colabfold_batch_bin,
                    colabfold_data_dir=settings.tools.colabfold_data_dir,
                    foldseek_bin=settings.tools.foldseek_bin,
                    msa_mode=str(settings.defaults.colabfold_msa_mode),
                    num_models=int(settings.defaults.colabfold_num_models),
                    num_recycle=int(settings.defaults.colabfold_num_recycle),
                    min_tmscore=float(
                        _plan_override(plan, "seed_structure_min_tmscore", settings.defaults.seed_structure_min_tmscore)
                    ),
                    topk_per_seed=int(
                        _plan_override(
                            plan,
                            "seed_structure_topk_per_seed",
                            settings.defaults.seed_structure_topk_per_seed,
                        )
                    ),
                    max_targets=int(
                        _plan_override(plan, "seed_structure_max_targets", settings.defaults.seed_structure_max_targets)
                    ),
                    software_version=__version__,
                )
            elif stage_name == "seed_recall_merge":
                if sequence_result is None or structure_recall_result is None:
                    raise RuntimeError("seed_recall_merge stage requires sequence and structure recall outputs")
                merge_result = run_seed_recall_merge_stage(
                    cluster_rep_faa=current_input,
                    sequence_hits_tsv=sequence_result["sequence_hits_tsv"],
                    structure_hits_tsv=structure_recall_result["structure_hits_tsv"],
                    stage_dir=stage_dirs[stage_name],
                    software_version=__version__,
                )
                seeded_merge_rows = list(merge_result["seed_rows"])
                current_input = Path(merge_result["seeded_targets_faa"])
                skip_downstream_for_empty_seeded_run = not seeded_merge_rows
            elif stage_name == "temstapro_screen":
                if skip_downstream_for_empty_seeded_run:
                    continue
                thermo_result = run_temstapro_screen(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    conda_bin=settings.tools.conda_bin,
                    conda_env_name=settings.tools.temstapro_conda_env_name,
                    temstapro_bin=settings.tools.temstapro_bin,
                    repo_root=settings.tools.temstapro_repo_root,
                    model_dir=settings.tools.temstapro_model_dir,
                    cache_dir=settings.tools.temstapro_cache_dir,
                    hf_home=settings.tools.temstapro_hf_home,
                    transformers_offline=settings.tools.temstapro_transformers_offline,
                    top_fraction=float(_plan_override(plan, "thermo_top_fraction", settings.defaults.thermo_top_fraction)),
                    min_score=float(_plan_override(plan, "thermo_min_score", settings.defaults.thermo_min_score)),
                    software_version=__version__,
                )
                current_input = Path(thermo_result["thermo_hits_faa"])
            elif stage_name == "protrek_recall":
                if skip_downstream_for_empty_seeded_run:
                    continue
                protrek_result = run_protrek_stage(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    python_bin=settings.tools.protrek_python_bin,
                    index_script="scripts/protrek_build_index.py",
                    query_script="scripts/protrek_query.py",
                    repo_root=settings.tools.protrek_repo_root,
                    weights_dir=settings.tools.protrek_weights_dir,
                    query_texts=list(settings.defaults.protrek_query_texts),
                    batch_size=int(_plan_override(plan, "protrek_batch_size", settings.defaults.protrek_batch_size)),
                    top_k=int(_plan_override(plan, "protrek_top_k", settings.defaults.protrek_top_k)),
                    software_version=__version__,
                )
            elif stage_name == "structure_predict":
                if skip_downstream_for_empty_seeded_run:
                    continue
                structure_result = run_structure_predict_stage(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    colabfold_batch_bin=settings.tools.colabfold_batch_bin,
                    colabfold_data_dir=settings.tools.colabfold_data_dir,
                    msa_mode=str(settings.defaults.colabfold_msa_mode),
                    num_models=int(settings.defaults.colabfold_num_models),
                    num_recycle=int(settings.defaults.colabfold_num_recycle),
                    software_version=__version__,
                )
            elif stage_name == "foldseek_confirm":
                if skip_downstream_for_empty_seeded_run:
                    continue
                if structure_result is None:
                    raise RuntimeError("foldseek_confirm stage requires structure outputs")
                foldseek_result = run_foldseek_stage(
                    structure_manifest=list(structure_result["structure_manifest"]),
                    stage_dir=stage_dirs[stage_name],
                    foldseek_bin=settings.tools.foldseek_bin,
                    database_path=settings.tools.foldseek_database_path,
                    topk=int(_plan_override(plan, "foldseek_topk", settings.defaults.foldseek_topk)),
                    min_tmscore=float(_plan_override(plan, "foldseek_min_tmscore", settings.defaults.foldseek_min_tmscore)),
                    software_version=__version__,
                )
            elif stage_name == "rerank_report":
                if skip_downstream_for_empty_seeded_run:
                    write_report_outputs(run_dir / "reports", run_dir.name, [])
                    continue
                if thermo_result is None or protrek_result is None or foldseek_result is None:
                    raise RuntimeError("rerank_report stage requires thermo, protrek, and foldseek outputs")
                hot_spring_ids = (
                    {record.protein_id for record in read_fasta(bundle["input_paths"][0])}
                    if bundle["bundle_type"] == "seeded_proteins"
                    else set()
                )
                combined_rows = combine_stage_scores(
                    thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
                    protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
                    foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
                    hot_spring_ids=hot_spring_ids,
                    seed_rows=seeded_merge_rows,
                )
                write_report_outputs(run_dir / "reports", run_dir.name, combined_rows)
            else:
                raise ValueError(f"unsupported stage '{stage_name}'")
    except Exception as exc:
        _write_stage_state(run_dir, "failed", active_stage, str(exc))
        raise

    _write_stage_state(run_dir, "succeeded", None, None)
