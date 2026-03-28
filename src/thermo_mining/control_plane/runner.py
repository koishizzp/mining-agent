import json
import os
from datetime import UTC, datetime
from pathlib import Path

from thermo_mining import __version__
from thermo_mining.control_plane.run_store import write_runtime_state
from thermo_mining.io_utils import read_fasta
from thermo_mining.control_plane.upstream_steps import run_fastp_stage, run_prodigal_stage, run_spades_stage
from thermo_mining.pipeline import _read_scores_tsv
from thermo_mining.reporting import write_report_outputs
from thermo_mining.settings import PlatformSettings, load_settings
from thermo_mining.steps.foldseek_client import run_foldseek_stage
from thermo_mining.steps.mmseqs_cluster import run_mmseqs_cluster
from thermo_mining.steps.prefilter import run_prefilter
from thermo_mining.steps.protrek_bridge import run_protrek_stage
from thermo_mining.steps.rerank import combine_stage_scores
from thermo_mining.steps.temstapro_screen import run_temstapro_screen


_STAGE_DIR_SUFFIXES = {
    "fastp": "fastp",
    "spades": "spades",
    "prodigal": "prodigal",
    "prefilter": "prefilter",
    "mmseqs_cluster": "cluster",
    "temstapro_screen": "temstapro",
    "protrek_recall": "protrek",
    "foldseek_confirm": "foldseek",
    "rerank_report": "report",
}


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


def _build_stage_dirs(run_dir: Path, stage_order: list[str]) -> dict[str, Path]:
    return {
        stage_name: run_dir / f"{index:02d}_{_STAGE_DIR_SUFFIXES[stage_name]}"
        for index, stage_name in enumerate(stage_order, start=1)
    }


def _plan_override(plan: dict[str, object], key: str, default: object) -> object:
    overrides = plan.get("parameter_overrides") or {}
    if not isinstance(overrides, dict):
        return default
    return overrides.get(key, default)


def _foldseek_manifest(input_faa: str | Path, stage_dir: str | Path) -> list[dict[str, str]]:
    structures_dir = Path(stage_dir) / "structures"
    return [
        {
            "protein_id": record.protein_id,
            "pdb_path": str(structures_dir / f"{record.protein_id}.pdb"),
        }
        for record in read_fasta(input_faa)
    ]


def run_job(run_dir: str | Path) -> None:
    run_dir = Path(run_dir)
    plan = _load_plan(run_dir)
    settings = _load_platform_settings()
    bundle = plan["input_items"][0]
    stage_order = list(plan["stage_order"])
    stage_dirs = _build_stage_dirs(run_dir, stage_order)
    current_input = Path(bundle["input_paths"][0])
    cleaned_reads: dict[str, Path] | None = None
    thermo_result: dict[str, Path] | None = None
    protrek_result: dict[str, Path] | None = None
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
                continue

            if stage_name == "spades":
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
                continue

            if stage_name == "prodigal":
                prodigal_result = run_prodigal_stage(
                    contigs_fa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    prodigal_bin=settings.tools.prodigal_bin,
                    software_version=__version__,
                )
                current_input = Path(prodigal_result["proteins_faa"])
                continue

            if stage_name == "prefilter":
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
                continue

            if stage_name == "mmseqs_cluster":
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
                continue

            if stage_name == "temstapro_screen":
                thermo_result = run_temstapro_screen(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    temstapro_bin=settings.tools.temstapro_bin,
                    model_dir="/models/temstapro/ProtTrans",
                    cache_dir="/tmp/temstapro_cache",
                    top_fraction=float(_plan_override(plan, "thermo_top_fraction", settings.defaults.thermo_top_fraction)),
                    min_score=float(_plan_override(plan, "thermo_min_score", settings.defaults.thermo_min_score)),
                    software_version=__version__,
                )
                current_input = Path(thermo_result["thermo_hits_faa"])
                continue

            if stage_name == "protrek_recall":
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
                continue

            if stage_name == "foldseek_confirm":
                foldseek_result = run_foldseek_stage(
                    structure_manifest=_foldseek_manifest(current_input, stage_dirs[stage_name]),
                    stage_dir=stage_dirs[stage_name],
                    base_url=settings.tools.foldseek_base_url,
                    database=str(_plan_override(plan, "foldseek_database", settings.defaults.foldseek_database)),
                    topk=int(_plan_override(plan, "foldseek_topk", settings.defaults.foldseek_topk)),
                    min_tmscore=float(_plan_override(plan, "foldseek_min_tmscore", settings.defaults.foldseek_min_tmscore)),
                    software_version=__version__,
                )
                continue

            if stage_name == "rerank_report":
                if thermo_result is None or protrek_result is None or foldseek_result is None:
                    raise RuntimeError("rerank_report stage requires thermo, protrek, and foldseek outputs")
                combined_rows = combine_stage_scores(
                    thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
                    protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
                    foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
                    hot_spring_ids=set(),
                )
                write_report_outputs(run_dir / "reports", run_dir.name, combined_rows)
                continue

            raise ValueError(f"unsupported stage '{stage_name}'")
    except Exception as exc:
        _write_stage_state(run_dir, "failed", active_stage, str(exc))
        raise

    _write_stage_state(run_dir, "succeeded", None, None)
