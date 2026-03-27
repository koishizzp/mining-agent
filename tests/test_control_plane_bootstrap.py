import pytest

from thermo_mining.cli import main
from thermo_mining.settings import load_settings


@pytest.mark.parametrize(
    ("argv", "command"),
    [
        (["serve"], "serve"),
        (["run-job", "--run-dir", "/tmp/run_001"], "run-job"),
    ],
)
def test_main_rejects_unimplemented_control_plane_commands(argv, command, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    assert f"command '{command}' is recognized but not implemented yet".lower() in capsys.readouterr().err.lower()


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
