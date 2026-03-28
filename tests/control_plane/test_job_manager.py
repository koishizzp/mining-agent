import pytest

from thermo_mining.control_plane.job_manager import ActiveRunConflict, JobManager
from thermo_mining.control_plane.run_store import create_pending_run
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


def test_confirm_run_builds_tmux_new_session_command(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(record.run_id)

    assert commands[0][:3] == ["tmux", "new-session", "-d"]
    assert record.run_id in " ".join(commands[0])


def test_confirm_run_rejects_second_active_run(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda cmd, check: None)
    first = create_pending_run(tmp_path, _build_plan())
    second = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(first.run_id)
    with pytest.raises(ActiveRunConflict):
        manager.confirm_run(second.run_id)
