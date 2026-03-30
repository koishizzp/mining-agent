# Thermo Mining Server Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python 3 server probe script that can run on a Linux server before this repository is cloned and emit `JSON`, draft `YAML`, and summary `TXT` artifacts for later deployment adaptation.

**Architecture:** Keep the probe as a single standard-library-only script at `scripts/server_probe.py` so the user can copy it to a target server and run it without installing this repo first. The script exposes small pure functions for report bootstrapping, deterministic tool detection, candidate detection, serialization, and CLI output, while `tests/test_server_probe.py` loads the script by path with `importlib` so it remains testable without turning it into a package module.

**Tech Stack:** Python 3.11+, pytest, importlib.util, tempfile/pathlib, json, urllib.request, shutil, subprocess

---

## File Map

- `scripts/server_probe.py`
  - Standalone probe entrypoint and all helper functions
  - Only Python standard library imports
  - Owns the status model, candidate lists, report assembly, JSON/YAML/TXT rendering, and CLI
- `tests/test_server_probe.py`
  - Loads the standalone script directly from disk
  - Covers report skeleton, deterministic tool probing, candidate probing, serialization, and CLI writing
- `README.md`
  - Documents how to run the probe, what files it emits, and which artifact is canonical for later agent work

### Task 1: Bootstrap The Standalone Probe Skeleton

**Files:**
- Create: `scripts/server_probe.py`
- Create: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing test**

```python
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
    assert report["deployment"]["config_path"]["status"] == "manual"
    assert report["service"]["host"] == {"status": "candidate", "value": "127.0.0.1"}
    assert report["service"]["port"] == {"status": "candidate", "value": 8000}
    assert report["warnings"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_probe.py::test_build_initial_report_contains_metadata_and_manual_deployment -v`
Expected: FAIL because `scripts/server_probe.py` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import platform
import socket
import sys
from datetime import datetime, timezone
from typing import Any


STATUS_VALUES = {"detected", "missing", "candidate", "manual"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def probe_item(status: str, **payload: Any) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError(f"unsupported status: {status}")
    item: dict[str, Any] = {"status": status}
    item.update(payload)
    return item


def build_initial_report() -> dict[str, Any]:
    return {
        "metadata": {
            "hostname": socket.gethostname(),
            "user": getpass.getuser(),
            "cwd": os.getcwd(),
            "generated_at": _utc_now_iso(),
            "python3_path": sys.executable,
            "python3_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "deployment": {
            "repo_root": probe_item("manual", value="__MANUAL__: choose final clone path"),
            "config_path": probe_item("manual", value="__MANUAL__: choose final config path"),
        },
        "tools": {},
        "protrek": {},
        "foldseek": {},
        "runtime": {},
        "service": {
            "host": probe_item("candidate", value="127.0.0.1"),
            "port": probe_item("candidate", value=8000),
        },
        "warnings": [],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe a thermo-mining server before repo clone.")
    parser.add_argument("--output-dir", default="thermo_server_probe")
    return parser.parse_args(argv)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_probe.py::test_build_initial_report_contains_metadata_and_manual_deployment -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): bootstrap standalone probe skeleton"
```

### Task 2: Add Deterministic Tool Detection And Version Capture

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_probe.py::test_probe_tools_marks_detected_and_missing -v`
Expected: FAIL because `probe_tools` and `capture_version_text` are not defined yet

- [ ] **Step 3: Write minimal implementation**

```python
import shutil
import subprocess
from pathlib import Path


TOOL_COMMANDS = {
    "tmux": "tmux",
    "fastp": "fastp",
    "spades_py": "spades.py",
    "prodigal": "prodigal",
    "mmseqs": "mmseqs",
    "temstapro": "temstapro",
}


def capture_version_text(path: str) -> str | None:
    for args in ([path, "--version"], [path, "-v"], [path, "version"]):
        try:
            completed = subprocess.run(args, capture_output=True, text=True, check=False, timeout=2)
        except OSError:
            return None
        output = (completed.stdout or completed.stderr).strip()
        if output:
            return output.splitlines()[0]
    return None


def probe_tools() -> dict[str, dict[str, Any]]:
    tools: dict[str, dict[str, Any]] = {}
    for key, command in TOOL_COMMANDS.items():
        resolved = shutil.which(command)
        if resolved is None:
            tools[key] = probe_item("missing", path=None, version_text=None)
            continue
        tools[key] = probe_item(
            "detected",
            path=str(Path(resolved)),
            version_text=capture_version_text(resolved),
        )
    return tools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_probe.py::test_probe_tools_marks_detected_and_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): detect tool binaries"
```

### Task 3: Add Candidate Detection For ProTrek, Runtime Roots, And Foldseek

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_probe.py::test_add_candidate_sections_records_protrek_runtime_and_foldseek -v`
Expected: FAIL because the candidate lists and `add_candidate_sections` do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


PROTREK_ROOT_CANDIDATES = [
    Path("/srv/ProTrek"),
    Path("/opt/ProTrek"),
    Path("/mnt/disk1/ProTrek"),
    Path("/mnt/disk2/ProTrek"),
    Path("/mnt/disk3/ProTrek"),
    Path("/mnt/disk4/ProTrek"),
]
PROTREK_PYTHON_CANDIDATES = [
    Path("/opt/protrek/bin/python"),
    Path("/srv/ProTrek/.venv/bin/python"),
    Path("/usr/bin/python3"),
]
RUNTIME_DATA_CANDIDATES = [
    Path("/mnt/disk2/thermo-inputs"),
    Path("/mnt/disk3/thermo-inputs"),
]
RUNTIME_RUNS_CANDIDATES = [
    Path("/mnt/disk4/thermo-runs"),
    Path("/mnt/disk3/thermo-runs"),
]
FOLDSEEK_DEFAULT_URL = "http://127.0.0.1:8100"


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def foldseek_candidate_reachable(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.5):
            return True
    except (OSError, URLError):
        return False


def add_candidate_sections(report: dict[str, Any]) -> None:
    protrek_root = _first_existing(PROTREK_ROOT_CANDIDATES)
    protrek_python = _first_existing(PROTREK_PYTHON_CANDIDATES)
    weights_dir = None if protrek_root is None else _first_existing([protrek_root / "weights" / "ProTrek_650M"])

    report["protrek"] = {
        "repo_root": probe_item("candidate", path=str(protrek_root)) if protrek_root else probe_item("missing", path=None),
        "python_bin": probe_item("candidate", path=str(protrek_python)) if protrek_python else probe_item("missing", path=None),
        "weights_dir": probe_item("candidate", path=str(weights_dir)) if weights_dir else probe_item("missing", path=None),
    }

    data_root = _first_existing(RUNTIME_DATA_CANDIDATES)
    runs_root = _first_existing(RUNTIME_RUNS_CANDIDATES)
    report["runtime"] = {
        "data_root": probe_item("candidate", value=str(data_root)) if data_root else probe_item("manual", value="__MANUAL__: choose final data directory"),
        "runs_root": probe_item("candidate", value=str(runs_root)) if runs_root else probe_item("manual", value="__MANUAL__: choose final runs directory"),
        "log_path": probe_item("candidate", value=str(runs_root / "platform.log")) if runs_root else probe_item("manual", value="__MANUAL__: choose final log path"),
    }

    if foldseek_candidate_reachable(FOLDSEEK_DEFAULT_URL):
        report["foldseek"] = {
            "base_url": probe_item("candidate", value=FOLDSEEK_DEFAULT_URL, connectivity="reachable"),
        }
    else:
        report["foldseek"] = {
            "base_url": probe_item("manual", value="__MANUAL__: set Foldseek service URL", connectivity="unknown"),
        }

    if protrek_root is None:
        report["warnings"].append("ProTrek repo root not found in the bounded candidate list.")
    if runs_root is None:
        report["warnings"].append("No candidate runs_root was found; choose one manually.")
    if report["foldseek"]["base_url"]["status"] == "manual":
        report["warnings"].append("Foldseek base URL remains manual because no local default candidate responded.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_probe.py::test_add_candidate_sections_records_protrek_runtime_and_foldseek -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): add candidate environment probing"
```

### Task 4: Write JSON, YAML, TXT Artifacts And Document Usage

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
import json


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

    monkeypatch.setattr(probe, "collect_probe_report", lambda: report)

    exit_code = probe.main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert json.loads((tmp_path / "server_probe.json").read_text(encoding="utf-8"))["tools"]["tmux"]["path"] == "/usr/bin/tmux"
    yaml_text = (tmp_path / "platform.server-draft.yaml").read_text(encoding="utf-8")
    assert "tmux_bin: /usr/bin/tmux" in yaml_text
    assert 'foldseek_base_url: "__MANUAL__: set Foldseek service URL"' in yaml_text
    summary_text = (tmp_path / "server_probe.txt").read_text(encoding="utf-8")
    assert "server probe completed" in summary_text.lower()
    assert "repo_root: manual" in summary_text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_probe.py::test_main_writes_json_yaml_and_summary_bundle -v`
Expected: FAIL because `collect_probe_report`, `write_probe_bundle`, and `main` are incomplete

- [ ] **Step 3: Write minimal implementation**

```python
import json
from pathlib import Path


def collect_probe_report() -> dict[str, Any]:
    report = build_initial_report()
    report["tools"] = probe_tools()
    add_candidate_sections(report)
    return report


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text.startswith("__MANUAL__:") or ":" in text or "#" in text:
        return json.dumps(text)
    return text


def render_platform_yaml(report: dict[str, Any]) -> str:
    lines = [
        "llm:",
        "  model: gpt-4o-mini",
        "  api_key: null",
        "  base_url: https://api.openai.com/v1",
        "",
        "runtime:",
        f"  data_root: {_yaml_scalar(report['runtime']['data_root'].get('value'))}",
        f"  runs_root: {_yaml_scalar(report['runtime']['runs_root'].get('value'))}",
        "",
        "service:",
        f"  host: {_yaml_scalar(report['service']['host'].get('value'))}",
        f"  port: {_yaml_scalar(report['service']['port'].get('value'))}",
        "",
        "logging:",
        f"  log_path: {_yaml_scalar(report['runtime']['log_path'].get('value'))}",
        "",
        "tools:",
        f"  fastp_bin: {_yaml_scalar(report['tools']['fastp'].get('path') or '__MANUAL__: set fastp path')}",
        f"  spades_bin: {_yaml_scalar(report['tools']['spades_py'].get('path') or '__MANUAL__: set spades.py path')}",
        f"  prodigal_bin: {_yaml_scalar(report['tools']['prodigal'].get('path') or '__MANUAL__: set prodigal path')}",
        f"  mmseqs_bin: {_yaml_scalar(report['tools']['mmseqs'].get('path') or '__MANUAL__: set mmseqs path')}",
        f"  temstapro_bin: {_yaml_scalar(report['tools']['temstapro'].get('path') or '__MANUAL__: set temstapro path')}",
        f"  protrek_python_bin: {_yaml_scalar(report['protrek']['python_bin'].get('path') or '__MANUAL__: set ProTrek python path')}",
        f"  protrek_repo_root: {_yaml_scalar(report['protrek']['repo_root'].get('path') or '__MANUAL__: set ProTrek repo root')}",
        f"  protrek_weights_dir: {_yaml_scalar(report['protrek']['weights_dir'].get('path') or '__MANUAL__: set ProTrek weights dir')}",
        f"  foldseek_base_url: {_yaml_scalar(report['foldseek']['base_url'].get('value'))}",
        f"  tmux_bin: {_yaml_scalar(report['tools']['tmux'].get('path') or '__MANUAL__: set tmux path')}",
        "",
        "defaults:",
        "  prefilter_min_length: 80",
        "  prefilter_max_length: 1200",
        "  prefilter_max_single_residue_fraction: 0.7",
        "  cluster_min_seq_id: 0.9",
        "  cluster_coverage: 0.8",
        "  cluster_threads: 64",
        "  thermo_top_fraction: 0.1",
        "  thermo_min_score: 0.5",
        "  protrek_query_texts:",
        "    - thermostable enzyme",
        "    - heat-stable protein",
        "  protrek_batch_size: 8",
        "  protrek_top_k: 50",
        "  foldseek_database: afdb50",
        "  foldseek_topk: 5",
        "  foldseek_min_tmscore: 0.6",
    ]
    return "\n".join(lines) + "\n"


def render_summary_text(report: dict[str, Any]) -> str:
    lines = [
        "Server probe completed.",
        f"host: {report['metadata']['hostname']}",
        f"user: {report['metadata']['user']}",
        f"repo_root: {report['deployment']['repo_root']['status']}",
        f"config_path: {report['deployment']['config_path']['status']}",
        f"tmux: {report['tools']['tmux']['status']}",
        f"foldseek_base_url: {report['foldseek']['base_url']['status']}",
    ]
    if report["warnings"]:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def write_probe_bundle(output_dir: Path, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "server_probe.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "platform.server-draft.yaml").write_text(render_platform_yaml(report), encoding="utf-8")
    (output_dir / "server_probe.txt").write_text(render_summary_text(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_probe_report()
    write_probe_bundle(Path(args.output_dir), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```markdown
# Thermo Mining

## Server Probe

Run the standalone probe on the target Linux server before cloning or
configuring this repository:

```bash
python3 scripts/server_probe.py --output-dir ./thermo_server_probe
```

The command writes:

- `server_probe.json` - canonical structured artifact for later agent work
- `platform.server-draft.yaml` - draft config matching this repo's config shape
- `server_probe.txt` - short human-readable summary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_probe.py::test_main_writes_json_yaml_and_summary_bundle -v`
Expected: PASS

- [ ] **Step 5: Run the full probe test file**

Run: `pytest tests/test_server_probe.py -v`
Expected: PASS

- [ ] **Step 6: Run the full project test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py README.md
git commit -m "feat(server-probe): write probe artifacts"
```

## Self-Review

### Spec coverage

- Goal and pre-clone constraint: Task 1 and Task 4
- Structure-first outputs (`JSON`, draft `YAML`, summary `TXT`): Task 4
- Closed status model (`detected`, `missing`, `candidate`, `manual`): Task 1
- Deterministic tool detection and version capture: Task 2
- Bounded candidate detection for ProTrek, runtime roots, and Foldseek: Task 3
- Manual-only deployment fields: Task 1 and Task 4
- Safety boundary of no installs / no service mutation / no broad filesystem crawl: Task 3 and Task 4
- Error handling separation between missing environment pieces and probe failure: Task 4
- Human workflow and README usage: Task 4

No spec section is left without an implementation task.

### Placeholder scan

There are no `TBD`, `TODO`, `implement later`, or cross-task "same as above"
placeholders in this plan. Each code-changing step includes concrete test code,
concrete implementation code, and an exact verification command.

### Type consistency

- The probe status values remain exactly `detected`, `missing`, `candidate`,
  and `manual` throughout the plan
- `server_probe.json`, `platform.server-draft.yaml`, and `server_probe.txt`
  are the only emitted artifact names throughout the plan
- The standalone script path remains `scripts/server_probe.py` in every task
- Deployment-only fields (`repo_root`, `config_path`) stay in the JSON/TXT
  report and are not introduced as extra top-level YAML config sections
