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
