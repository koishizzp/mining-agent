import importlib.util
from pathlib import Path


def load_probe_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "server_probe.py"
    spec = importlib.util.spec_from_file_location("thermo_server_probe", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_initial_report_contains_metadata_and_manual_deployment(monkeypatch):
    probe = load_probe_module()

    monkeypatch.setattr(probe.socket, "gethostname", lambda: "thermo-box")
    monkeypatch.setattr(probe.getpass, "getuser", lambda: "ubuntu")
    monkeypatch.setattr(probe.os, "getcwd", lambda: "/home/ubuntu")
    monkeypatch.setattr(probe.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(probe.platform, "platform", lambda: "Linux-6.8")
    monkeypatch.setattr(probe, "_utc_now_iso", lambda: "2026-03-30T12:00:00+00:00")

    report = probe.build_initial_report()

    assert report["metadata"]["hostname"] == "thermo-box"
    assert report["metadata"]["user"] == "ubuntu"
    assert report["metadata"]["cwd"] == "/home/ubuntu"
    assert report["metadata"]["python3_path"] == "/usr/bin/python3"
    assert report["metadata"]["generated_at"] == "2026-03-30T12:00:00+00:00"
    assert report["deployment"]["repo_root"]["status"] == "manual"
    assert report["deployment"]["repo_root"]["value"] == "__MANUAL__: choose final clone path"
    assert report["deployment"]["config_path"]["status"] == "manual"
    assert report["deployment"]["config_path"]["value"] == "__MANUAL__: choose final config path"
    assert report["service"]["host"] == {"status": "candidate", "value": "127.0.0.1"}
    assert report["service"]["port"] == {"status": "candidate", "value": 8000}
    assert report["tools"] == {}
    assert report["protrek"] == {}
    assert report["foldseek"] == {}
    assert report["runtime"] == {}
    assert report["warnings"] == []


def test_probe_tools_marks_detected_and_missing(monkeypatch):
    probe = load_probe_module()

    monkeypatch.setattr(
        probe.shutil,
        "which",
        lambda name: {
            "tmux": "/usr/bin/tmux",
            "fastp": "/usr/bin/fastp",
            "spades.py": "/usr/bin/spades.py",
            "prodigal": "/usr/bin/prodigal",
            "mmseqs": "/usr/bin/mmseqs",
        }.get(name),
    )
    monkeypatch.setattr(probe, "capture_version_text", lambda path: f"{Path(path).name} 1.0")

    tools = probe.probe_tools()

    assert tools["tmux"]["status"] == "detected"
    assert tools["tmux"]["path"] == "/usr/bin/tmux"
    assert tools["tmux"]["version_text"] == "tmux 1.0"
    assert tools["fastp"]["status"] == "detected"
    assert tools["temstapro"]["status"] == "missing"
    assert tools["temstapro"]["path"] is None
