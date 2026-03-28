import pytest
from pathlib import Path

from thermo_mining.cli import build_parser, main
from thermo_mining.control_plane.run_store import read_active_run, set_active_run
from thermo_mining.settings import load_settings


def test_build_parser_accepts_control_plane_commands_with_explicit_flags():
    parser = build_parser()

    serve_args = parser.parse_args(
        ["serve", "--host", "0.0.0.0", "--port", "9000", "--config", "config/platform.example.yaml"]
    )
    run_job_args = parser.parse_args(
        ["run-job", "--run-dir", "/tmp/run_001", "--config", "config/platform.example.yaml"]
    )

    assert serve_args.command == "serve"
    assert serve_args.host == "0.0.0.0"
    assert serve_args.port == 9000
    assert serve_args.config == "config/platform.example.yaml"
    assert run_job_args.command == "run-job"
    assert run_job_args.run_dir == "/tmp/run_001"
    assert run_job_args.config == "config/platform.example.yaml"


@pytest.mark.parametrize(
    ("argv", "command"),
    [
        (["serve"], "serve"),
    ],
)
def test_main_rejects_unimplemented_control_plane_commands(argv, command, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    assert f"command '{command}' is recognized but not implemented yet".lower() in capsys.readouterr().err.lower()


def test_main_dispatches_run_job_and_clears_active_marker(tmp_path, monkeypatch):
    called: list[str] = []
    run_dir = tmp_path / "run_001"

    def _fake_run_job(run_dir):
        called.append(str(run_dir))

    set_active_run(tmp_path, "run_001")
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_job", _fake_run_job)

    result = main(["run-job", "--run-dir", str(run_dir)])

    assert result is None
    assert len(called) == 1
    assert Path(called[0]) == run_dir
    assert read_active_run(tmp_path) is None


def test_main_run_job_clears_active_marker_on_failure(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_001"

    def _fake_run_job(run_dir):
        raise RuntimeError("boom")

    set_active_run(tmp_path, "run_001")
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_job", _fake_run_job)

    with pytest.raises(RuntimeError, match="boom"):
        main(["run-job", "--run-dir", str(run_dir)])

    assert read_active_run(tmp_path) is None


def test_main_run_job_preserves_different_active_marker(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_001"

    monkeypatch.setattr("thermo_mining.control_plane.runner.run_job", lambda run_dir: None)
    set_active_run(tmp_path, "run_other")

    main(["run-job", "--run-dir", str(run_dir)])

    assert read_active_run(tmp_path) == "run_other"


def test_load_settings_reads_tmux_bin_and_service_port(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
service:
  host: 0.0.0.0
  port: 9000
tools:
  tmux_bin: /usr/bin/tmux
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.service.host == "0.0.0.0"
    assert settings.service.port == 9000
    assert settings.tools.tmux_bin == "/usr/bin/tmux"


def test_load_settings_tmux_bin_env_override(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("tools:\n  tmux_bin: /usr/bin/tmux\n", encoding="utf-8")
    monkeypatch.setenv("THERMO_TMUX_BIN", "/custom/tmux")

    settings = load_settings(config_path)

    assert settings.tools.tmux_bin == "/custom/tmux"
