#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


STATUS_VALUES = {"detected", "missing", "candidate", "manual"}
TOOL_COMMANDS = {
    "tmux": "tmux",
    "fastp": "fastp",
    "spades_py": "spades.py",
    "prodigal": "prodigal",
    "mmseqs": "mmseqs",
    "temstapro": "temstapro",
}
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
            path=resolved,
            version_text=capture_version_text(resolved),
        )
    return tools


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe a thermo-mining server before repo clone.")
    parser.add_argument("--output-dir", default="thermo_server_probe")
    return parser.parse_args(argv)
