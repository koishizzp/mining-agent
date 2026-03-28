import subprocess

import pytest

from thermo_mining.control_plane.job_manager import ActiveRunConflict, JobManager
from thermo_mining.control_plane.run_store import create_pending_run, read_active_run, set_active_run
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


def test_confirm_run_same_run_id_is_idempotent(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(record.run_id)
    manager.confirm_run(record.run_id)

    assert len(commands) == 1


def test_confirm_run_claims_active_marker_before_tmux_start(tmp_path, monkeypatch):
    seen_active: list[str | None] = []

    def _fake_run(cmd: list[str], check: bool) -> None:
        seen_active.append(read_active_run(tmp_path))

    monkeypatch.setattr("subprocess.run", _fake_run)
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(record.run_id)

    assert seen_active == [record.run_id]


def test_confirm_run_tmux_failure_clears_active_marker(tmp_path, monkeypatch):
    def _fake_run(cmd: list[str], check: bool) -> None:
        assert read_active_run(tmp_path) == record.run_id
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("subprocess.run", _fake_run)
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    with pytest.raises(subprocess.CalledProcessError):
        manager.confirm_run(record.run_id)

    assert read_active_run(tmp_path) is None


def test_stop_run_sends_interrupt_and_clears_active_marker(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    run_id = "run_1234abcd"
    set_active_run(tmp_path, run_id)
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.stop_run(run_id)

    assert commands == [["tmux", "send-keys", "-t", "thermo_run_1234abcd", "C-c"]]
    assert read_active_run(tmp_path) is None


def test_terminate_run_kills_session_and_clears_active_marker(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    run_id = "run_1234abcd"
    set_active_run(tmp_path, run_id)
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.terminate_run(run_id)

    assert commands == [["tmux", "kill-session", "-t", "thermo_run_1234abcd"]]
    assert read_active_run(tmp_path) is None


def test_resume_run_confirms_run(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    session_name = manager.resume_run(record.run_id)

    assert session_name == f"thermo_{record.run_id}"
    assert commands[0][:3] == ["tmux", "new-session", "-d"]
