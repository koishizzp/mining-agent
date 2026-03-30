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


def test_add_candidate_sections_records_protrek_runtime_and_foldseek(monkeypatch, tmp_path):
    probe = load_probe_module()

    protrek_root = tmp_path / "srv" / "ProTrek"
    protrek_python = protrek_root / ".venv" / "bin" / "python"
    weights_dir = protrek_root / "weights" / "ProTrek_650M"
    data_root = tmp_path / "mnt" / "disk2" / "thermo-inputs"
    runs_root = tmp_path / "mnt" / "disk4" / "thermo-runs"

    protrek_python.parent.mkdir(parents=True)
    weights_dir.mkdir(parents=True)
    data_root.mkdir(parents=True)
    runs_root.mkdir(parents=True)
    protrek_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe, "PROTREK_ROOT_CANDIDATES", [protrek_root])
    monkeypatch.setattr(probe, "PROTREK_PYTHON_CANDIDATES", [protrek_python])
    monkeypatch.setattr(probe, "RUNTIME_DATA_CANDIDATES", [data_root])
    monkeypatch.setattr(probe, "RUNTIME_RUNS_CANDIDATES", [runs_root])
    monkeypatch.setattr(probe, "foldseek_candidate_reachable", lambda url: True)

    report = probe.build_initial_report()
    probe.add_candidate_sections(report)

    assert report["protrek"]["repo_root"]["status"] == "candidate"
    assert report["protrek"]["repo_root"]["path"] == str(protrek_root)
    assert report["protrek"]["python_bin"]["path"] == str(protrek_python)
    assert report["protrek"]["weights_dir"]["path"] == str(weights_dir)
    assert report["runtime"]["data_root"]["value"] == str(data_root)
    assert report["runtime"]["runs_root"]["value"] == str(runs_root)
    assert report["runtime"]["log_path"]["value"] == str(runs_root / "platform.log")
    assert report["foldseek"]["base_url"]["status"] == "candidate"
    assert report["foldseek"]["base_url"]["value"] == "http://127.0.0.1:8100"
    assert report["warnings"] == []
