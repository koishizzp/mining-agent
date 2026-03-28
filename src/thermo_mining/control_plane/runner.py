import json
from datetime import UTC, datetime
from pathlib import Path

from thermo_mining import __version__
from thermo_mining.control_plane.run_store import write_runtime_state
from thermo_mining.io_utils import read_fasta
from thermo_mining.control_plane.upstream_steps import run_fastp_stage, run_prodigal_stage, run_spades_stage
from thermo_mining.pipeline import _read_scores_tsv
from thermo_mining.reporting import write_report_outputs
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
                    fastp_bin="fastp",
                )
                continue

            if stage_name == "spades":
                if cleaned_reads is None:
                    raise RuntimeError("spades stage requires fastp outputs")
                spades_result = run_spades_stage(
                    read1=cleaned_reads["read1"],
                    read2=cleaned_reads["read2"],
                    stage_dir=stage_dirs[stage_name],
                    spades_bin="spades.py",
                    threads=32,
                )
                current_input = Path(spades_result["contigs_fa"])
                continue

            if stage_name == "prodigal":
                prodigal_result = run_prodigal_stage(
                    contigs_fa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    prodigal_bin="prodigal",
                    software_version=__version__,
                )
                current_input = Path(prodigal_result["proteins_faa"])
                continue

            if stage_name == "prefilter":
                prefilter_result = run_prefilter(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    min_length=int(_plan_override(plan, "prefilter_min_length", 80)),
                    max_length=int(_plan_override(plan, "prefilter_max_length", 1200)),
                    max_single_residue_fraction=float(_plan_override(plan, "prefilter_max_single_residue_fraction", 0.7)),
                    software_version=__version__,
                )
                current_input = Path(prefilter_result["filtered_faa"])
                continue

            if stage_name == "mmseqs_cluster":
                cluster_result = run_mmseqs_cluster(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    mmseqs_bin="mmseqs",
                    min_seq_id=0.9,
                    coverage=0.8,
                    threads=64,
                    software_version=__version__,
                )
                current_input = Path(cluster_result["cluster_rep_faa"])
                continue

            if stage_name == "temstapro_screen":
                thermo_result = run_temstapro_screen(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    temstapro_bin="temstapro",
                    model_dir="/models/temstapro/ProtTrans",
                    cache_dir="/tmp/temstapro_cache",
                    top_fraction=float(_plan_override(plan, "thermo_top_fraction", 0.1)),
                    min_score=float(_plan_override(plan, "thermo_min_score", 0.5)),
                    software_version=__version__,
                )
                current_input = Path(thermo_result["thermo_hits_faa"])
                continue

            if stage_name == "protrek_recall":
                protrek_result = run_protrek_stage(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    python_bin="python",
                    index_script="scripts/protrek_build_index.py",
                    query_script="scripts/protrek_query.py",
                    repo_root="/srv/ProTrek",
                    weights_dir="/srv/ProTrek/weights/ProTrek_650M",
                    query_texts=["thermostable enzyme"],
                    batch_size=8,
                    top_k=int(_plan_override(plan, "protrek_top_k", 50)),
                    software_version=__version__,
                )
                continue

            if stage_name == "foldseek_confirm":
                foldseek_result = run_foldseek_stage(
                    structure_manifest=_foldseek_manifest(current_input, stage_dirs[stage_name]),
                    stage_dir=stage_dirs[stage_name],
                    base_url="http://127.0.0.1:8100",
                    database="afdb50",
                    topk=int(_plan_override(plan, "foldseek_topk", 5)),
                    min_tmscore=float(_plan_override(plan, "foldseek_min_tmscore", 0.6)),
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
