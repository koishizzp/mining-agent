from thermo_mining.control_plane.run_store import (
    clear_active_run,
    create_pending_run,
    read_active_run,
    read_runtime_state,
    set_active_run,
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
    assert (run_dir / "runtime_state.json").exists()
    assert read_runtime_state(run_dir).status == "pending"


def test_active_run_lock_roundtrip(tmp_path):
    set_active_run(tmp_path, "run_001")
    assert read_active_run(tmp_path) == "run_001"
    clear_active_run(tmp_path)
    assert read_active_run(tmp_path) is None
