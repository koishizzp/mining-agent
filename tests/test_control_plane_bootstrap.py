from pathlib import Path
from types import SimpleNamespace

import pytest

from thermo_mining.cli import build_parser, main, serve_app
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


def test_cli_main_dispatches_serve_and_run_job(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "thermo_mining.cli.serve_app",
        lambda config_path, host, port: captured.update({"serve": (config_path, host, port)}),
    )
    monkeypatch.setattr(
        "thermo_mining.cli.run_job",
        lambda run_dir, config_path=None: captured.update({"run_job": (run_dir, config_path)}),
    )

    main(["serve", "--config", "config/platform.example.yaml", "--host", "0.0.0.0", "--port", "9000"])
    main(["run-job", "--config", "config/platform.example.yaml", "--run-dir", str(tmp_path / "run_001")])

    assert captured["serve"][1:] == ("0.0.0.0", 9000)
    assert str(tmp_path / "run_001") in str(captured["run_job"][0])


def test_serve_app_uses_config_defaults_when_host_and_port_omitted(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    config_path = tmp_path / "platform.yaml"

    monkeypatch.setattr(
        "thermo_mining.cli.load_settings",
        lambda path: SimpleNamespace(service=SimpleNamespace(host="0.0.0.0", port=9100)),
    )
    monkeypatch.setattr(
        "thermo_mining.cli.uvicorn.run",
        lambda app_path, factory, host, port: captured.update(
            {"app_path": app_path, "factory": factory, "host": host, "port": port}
        ),
    )

    serve_app(config_path, host=None, port=None)

    assert captured == {
        "app_path": "thermo_mining.web.app:create_app",
        "factory": True,
        "host": "0.0.0.0",
        "port": 9100,
    }


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


def test_control_plane_scripts_resolve_repo_root_and_check_live_pid():
    root = Path(__file__).resolve().parents[1]
    start_web = (root / "scripts" / "start_web.sh").read_text(encoding="utf-8")
    start_all = (root / "scripts" / "start_all.sh").read_text(encoding="utf-8")
    status = (root / "scripts" / "status.sh").read_text(encoding="utf-8")
    stop = (root / "scripts" / "stop.sh").read_text(encoding="utf-8")

    assert 'BASH_SOURCE[0]' in start_web
    assert 'REPO_ROOT=' in start_web
    assert 'CONFIG_PATH=' in start_web
    assert 'LOG_DIR=' in start_web
    assert 'SCRIPT_DIR=' in start_all
    assert 'kill -0' in status
    assert 'ps -p' in status
    assert 'kill -0' in stop
    assert 'ps -p' in stop
