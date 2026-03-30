import json
import importlib.util
from pathlib import Path


def load_probe_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "server_probe.py"
    spec = importlib.util.spec_from_file_location("thermo_server_probe", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_accepts_conda_prefix_and_name():
    probe = load_probe_module()

    args = probe.parse_args(["--output-dir", "out", "--conda-prefix", "/envs/thermo", "--conda-name", "thermo"])

    assert args.output_dir == "out"
    assert args.conda_prefix == "/envs/thermo"
    assert args.conda_name == "thermo"


def test_build_initial_report_includes_manual_conda_section(monkeypatch):
    probe = load_probe_module()

    monkeypatch.setattr(probe.socket, "gethostname", lambda: "thermo-box")
    monkeypatch.setattr(probe.getpass, "getuser", lambda: "ubuntu")
    monkeypatch.setattr(probe.os, "getcwd", lambda: "/home/ubuntu")
    monkeypatch.setattr(probe.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(probe.platform, "platform", lambda: "Linux-6.8")
    monkeypatch.setattr(probe, "_utc_now_iso", lambda: "2026-03-30T12:00:00+00:00")

    report = probe.build_initial_report()

    assert report["conda"] == {
        "requested_mode": "none",
        "requested_name": None,
        "requested_prefix": None,
        "resolved_prefix": None,
        "active_prefix": None,
        "active_env_name": None,
        "status": "manual",
        "notes": [],
    }


def test_resolve_conda_target_prefers_explicit_prefix(monkeypatch):
    probe = load_probe_module()

    monkeypatch.setenv("CONDA_PREFIX", "/envs/active")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "active")
    monkeypatch.setattr(probe, "path_exists", lambda path: str(path) == "/envs/thermo")
    monkeypatch.setattr(probe, "load_conda_env_prefixes", lambda: ["/envs/other"])

    args = probe.parse_args(["--conda-prefix", "/envs/thermo", "--conda-name", "other"])
    conda = probe.resolve_conda_target(args)

    assert conda["requested_mode"] == "prefix"
    assert conda["requested_prefix"] == "/envs/thermo"
    assert conda["requested_name"] is None
    assert conda["resolved_prefix"] == "/envs/thermo"
    assert conda["active_prefix"] == "/envs/active"
    assert conda["active_env_name"] == "active"
    assert conda["status"] == "detected"
    assert conda["notes"] == []


def test_resolve_conda_target_resolves_name_and_uses_active_env_fallback(monkeypatch):
    probe = load_probe_module()

    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
    monkeypatch.setattr(probe, "load_conda_env_prefixes", lambda: ["/opt/miniconda/envs/base", "/opt/miniconda/envs/thermo"])
    monkeypatch.setattr(probe, "path_exists", lambda path: True)

    named = probe.resolve_conda_target(probe.parse_args(["--conda-name", "thermo"]))
    assert named["requested_mode"] == "name"
    assert named["requested_name"] == "thermo"
    assert named["resolved_prefix"] == "/opt/miniconda/envs/thermo"
    assert named["status"] == "detected"

    monkeypatch.setenv("CONDA_PREFIX", "/envs/active")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "active")
    active = probe.resolve_conda_target(probe.parse_args([]))
    assert active["requested_mode"] == "active_env"
    assert active["resolved_prefix"] == "/envs/active"
    assert active["active_env_name"] == "active"
    assert active["status"] == "detected"


def test_probe_tools_prefers_resolved_conda_prefix(monkeypatch, tmp_path):
    probe = load_probe_module()

    env_prefix = tmp_path / "envs" / "thermo"
    env_bin = env_prefix / "bin"
    fastp_path = env_bin / "fastp"
    env_bin.mkdir(parents=True)
    fastp_path.write_text("", encoding="utf-8")

    conda = {
        "requested_mode": "prefix",
        "requested_name": None,
        "requested_prefix": str(env_prefix),
        "resolved_prefix": str(env_prefix),
        "active_prefix": None,
        "active_env_name": None,
        "status": "detected",
        "notes": [],
    }
    warnings: list[str] = []

    monkeypatch.setattr(probe.shutil, "which", lambda name: None)
    monkeypatch.setattr(probe, "capture_version_text", lambda path: f"{Path(path).name} 1.0")

    tools = probe.probe_tools(conda, warnings)

    assert tools["fastp"]["path"] == str(fastp_path)
    assert tools["fastp"]["source"] == "conda_prefix"
    assert tools["fastp"]["from_conda"] is True
    assert warnings == []


def test_probe_tools_warns_when_tool_falls_back_outside_conda(monkeypatch, tmp_path):
    probe = load_probe_module()

    env_prefix = tmp_path / "envs" / "thermo"
    env_prefix.mkdir(parents=True)
    conda = {
        "requested_mode": "prefix",
        "requested_name": None,
        "requested_prefix": str(env_prefix),
        "resolved_prefix": str(env_prefix),
        "active_prefix": None,
        "active_env_name": None,
        "status": "detected",
        "notes": [],
    }
    warnings: list[str] = []

    monkeypatch.setattr(probe.shutil, "which", lambda name: "/usr/bin/fastp" if name == "fastp" else None)
    monkeypatch.setattr(probe, "capture_version_text", lambda path: None)

    tools = probe.probe_tools(conda, warnings)

    assert tools["fastp"]["path"] == "/usr/bin/fastp"
    assert tools["fastp"]["source"] == "path"
    assert tools["fastp"]["from_conda"] is False
    assert any("fastp" in warning and "conda" in warning.lower() for warning in warnings)


def test_main_writes_conda_metadata_and_summary_lines(monkeypatch, tmp_path):
    probe = load_probe_module()

    report = probe.build_initial_report()
    report["conda"] = {
        "requested_mode": "prefix",
        "requested_name": None,
        "requested_prefix": "/envs/thermo",
        "resolved_prefix": "/envs/thermo",
        "active_prefix": None,
        "active_env_name": None,
        "status": "detected",
        "notes": [],
    }
    report["tools"] = {
        "tmux": {
            "status": "detected",
            "path": "/usr/bin/tmux",
            "version_text": "tmux 3.4",
            "source": "path",
            "from_conda": False,
        },
        "fastp": {
            "status": "detected",
            "path": "/envs/thermo/bin/fastp",
            "version_text": "fastp 0.23.4",
            "source": "conda_prefix",
            "from_conda": True,
        },
        "spades_py": {"status": "missing", "path": None, "version_text": None, "source": "missing", "from_conda": False},
        "prodigal": {"status": "missing", "path": None, "version_text": None, "source": "missing", "from_conda": False},
        "mmseqs": {"status": "missing", "path": None, "version_text": None, "source": "missing", "from_conda": False},
        "temstapro": {"status": "missing", "path": None, "version_text": None, "source": "missing", "from_conda": False},
    }
    report["runtime"] = {
        "data_root": {"status": "manual", "value": "__MANUAL__: choose final data directory"},
        "runs_root": {"status": "candidate", "value": "/mnt/disk4/thermo-runs"},
        "log_path": {"status": "candidate", "value": "/mnt/disk4/thermo-runs/platform.log"},
    }
    report["protrek"] = {
        "python_bin": {"status": "missing", "path": None},
        "repo_root": {"status": "missing", "path": None},
        "weights_dir": {"status": "missing", "path": None},
    }
    report["foldseek"] = {
        "base_url": {"status": "manual", "value": "__MANUAL__: set Foldseek service URL", "connectivity": "unknown"},
    }

    monkeypatch.setattr(probe, "collect_probe_report", lambda args: report)

    exit_code = probe.main(["--output-dir", str(tmp_path), "--conda-prefix", "/envs/thermo"])

    assert exit_code == 0
    payload = json.loads((tmp_path / "server_probe.json").read_text(encoding="utf-8"))
    assert payload["conda"]["resolved_prefix"] == "/envs/thermo"
    assert payload["tools"]["fastp"]["source"] == "conda_prefix"
    assert payload["tools"]["fastp"]["from_conda"] is True
    summary_text = (tmp_path / "server_probe.txt").read_text(encoding="utf-8").lower()
    assert "conda request: prefix" in summary_text
    assert "conda resolved prefix: /envs/thermo" in summary_text
    assert "fastp source: conda_prefix" in summary_text


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


def test_main_writes_json_yaml_and_summary_bundle(monkeypatch, tmp_path):
    probe = load_probe_module()

    report = probe.build_initial_report()
    report["tools"] = {
        "tmux": {"status": "detected", "path": "/usr/bin/tmux", "version_text": "tmux 3.4"},
        "fastp": {"status": "missing", "path": None, "version_text": None},
        "spades_py": {"status": "missing", "path": None, "version_text": None},
        "prodigal": {"status": "missing", "path": None, "version_text": None},
        "mmseqs": {"status": "missing", "path": None, "version_text": None},
        "temstapro": {"status": "missing", "path": None, "version_text": None},
    }
    report["runtime"] = {
        "data_root": {"status": "manual", "value": "__MANUAL__: choose final data directory"},
        "runs_root": {"status": "candidate", "value": "/mnt/disk4/thermo-runs"},
        "log_path": {"status": "candidate", "value": "/mnt/disk4/thermo-runs/platform.log"},
    }
    report["protrek"] = {
        "python_bin": {"status": "missing", "path": None},
        "repo_root": {"status": "missing", "path": None},
        "weights_dir": {"status": "missing", "path": None},
    }
    report["foldseek"] = {
        "base_url": {"status": "manual", "value": "__MANUAL__: set Foldseek service URL", "connectivity": "unknown"},
    }

    monkeypatch.setattr(probe, "collect_probe_report", lambda args: report)

    exit_code = probe.main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert json.loads((tmp_path / "server_probe.json").read_text(encoding="utf-8"))["tools"]["tmux"]["path"] == "/usr/bin/tmux"
    yaml_text = (tmp_path / "platform.server-draft.yaml").read_text(encoding="utf-8")
    assert "tmux_bin: /usr/bin/tmux" in yaml_text
    assert 'foldseek_base_url: "__MANUAL__: set Foldseek service URL"' in yaml_text
    summary_text = (tmp_path / "server_probe.txt").read_text(encoding="utf-8")
    assert "server probe completed" in summary_text.lower()
    assert "repo_root: manual" in summary_text.lower()
