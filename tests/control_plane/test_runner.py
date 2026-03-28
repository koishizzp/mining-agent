import json

from thermo_mining.control_plane.run_store import create_pending_run
from thermo_mining.control_plane.runner import run_job
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _make_plan(bundle_type: str, input_paths: list[str], output_root: str) -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type=bundle_type,
        sample_id="S01",
        input_paths=input_paths,
        metadata={},
        output_root=output_root,
    )
    return ExecutionPlan(
        bundle_type=bundle_type,
        input_items=[bundle],
        stage_order=build_stage_order(bundle_type),
        parameter_overrides={},
        output_root=output_root,
        resume_policy="if_possible",
        explanation="test",
    )


def test_run_job_executes_expected_stage_order_for_contigs(tmp_path, monkeypatch):
    plan = _make_plan("contigs", ["/mnt/disk2/S01_contigs.fa"], "/runs/S01")
    record = create_pending_run(tmp_path, plan)
    calls: list[str] = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prodigal_stage",
        lambda **kwargs: calls.append("prodigal") or {"proteins_faa": tmp_path / "proteins.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": tmp_path / "filtered.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": tmp_path / "cluster.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_temstapro_screen",
        lambda **kwargs: calls.append("temstapro")
        or {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.write_report_outputs",
        lambda *args, **kwargs: calls.append("report") or {"summary_md": tmp_path / "summary.md"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.combine_stage_scores",
        lambda **kwargs: [
            {
                "protein_id": "p1",
                "tier": "Tier 1",
                "final_score": 0.9,
                "thermo_score": 0.9,
                "protrek_score": 0.9,
                "foldseek_score": 0.9,
                "origin_bonus": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner._read_scores_tsv",
        lambda path: [
            {
                "protein_id": "p1",
                "thermo_score": "0.9",
                "protrek_score": "0.9",
                "foldseek_score": "0.9",
            }
        ],
    )

    run_job(record.run_dir)

    state = json.loads((tmp_path / record.run_id / "runtime_state.json").read_text(encoding="utf-8"))
    assert calls == ["prodigal", "prefilter", "mmseqs", "temstapro", "protrek", "foldseek", "report"]
    assert state["status"] == "succeeded"
