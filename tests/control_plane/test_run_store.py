import json

from thermo_mining.control_plane.run_store import (
    clear_active_run,
    create_pending_run,
    list_artifacts,
    read_active_run,
    read_runtime_state,
    set_active_run,
    write_runtime_state,
)
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _build_plan() -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    return ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="test plan",
    )


def test_create_pending_run_writes_run_layout(tmp_path):
    record = create_pending_run(tmp_path, _build_plan())

    run_dir = tmp_path / record.run_id
    assert (run_dir / "execution_plan.json").exists()
    assert (run_dir / "bundle_manifest.json").exists()
    assert (run_dir / "runtime_state.json").exists()
    assert read_runtime_state(run_dir).status == "pending"

    bundle_manifest = json.loads((run_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    assert bundle_manifest == [
        {
            "bundle_type": "proteins",
            "sample_id": "S01",
            "input_paths": ["/mnt/disk2/S01.faa"],
            "seed_paths": [],
            "metadata": {},
            "output_root": "/runs/S01",
        }
    ]


def test_active_run_lock_roundtrip(tmp_path):
    set_active_run(tmp_path, "run_001")
    assert read_active_run(tmp_path) == "run_001"
    clear_active_run(tmp_path)
    assert read_active_run(tmp_path) is None


def test_runtime_state_write_read_preserves_claimed_fields(tmp_path):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    payload = {
        "run_id": "run_001",
        "status": "running",
        "created_at": "2026-03-28T00:00:00+00:00",
        "confirmed_at": "2026-03-28T00:05:00+00:00",
        "tmux_session": "tmux_run_001",
        "active_stage": "prefilter",
        "stages": [{"stage_name": "prefilter", "status": "running"}],
    }

    write_runtime_state(run_dir, payload)
    record = read_runtime_state(run_dir)

    assert record.run_id == "run_001"
    assert record.status == "running"
    assert record.created_at == "2026-03-28T00:00:00+00:00"
    assert record.confirmed_at == "2026-03-28T00:05:00+00:00"
    assert record.tmux_session == "tmux_run_001"
    assert record.run_dir == str(run_dir)


def test_list_artifacts_returns_artifacts_and_reports_files(tmp_path):
    run_dir = tmp_path / "run_001"
    artifacts_dir = run_dir / "artifacts"
    reports_dir = run_dir / "reports"
    artifacts_dir.mkdir(parents=True)
    reports_dir.mkdir()

    fasta_path = artifacts_dir / "hits.fasta"
    report_path = reports_dir / "summary.md"
    fasta_path.write_text(">p1\nMSTNPKPQR\n", encoding="utf-8")
    report_path.write_text("# Summary\n", encoding="utf-8")

    rows = list_artifacts(run_dir)

    by_path = {entry.path: entry for entry in rows}
    assert set(by_path) == {str(fasta_path), str(report_path)}
    assert by_path[str(fasta_path)].kind == "fasta"
    assert by_path[str(fasta_path)].label == "hits.fasta"
    assert by_path[str(fasta_path)].size == fasta_path.stat().st_size
    assert by_path[str(report_path)].kind == "md"
    assert by_path[str(report_path)].label == "summary.md"
    assert by_path[str(report_path)].size == report_path.stat().st_size
