from thermo_mining.cli import build_parser
from thermo_mining.settings import load_settings


def test_build_parser_accepts_control_plane_commands():
    parser = build_parser()

    serve_args = parser.parse_args(["serve"])
    run_job_args = parser.parse_args(["run-job", "--run-dir", "/tmp/run_001"])

    assert serve_args.command == "serve"
    assert run_job_args.command == "run-job"
    assert run_job_args.run_dir == "/tmp/run_001"


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
