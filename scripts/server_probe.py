#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
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
        "conda": {
            "requested_mode": "none",
            "requested_name": None,
            "requested_prefix": None,
            "resolved_prefix": None,
            "active_prefix": None,
            "active_env_name": None,
            "status": "manual",
            "notes": [],
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


def _conda_tool_path(conda: dict[str, Any], command: str) -> tuple[str | None, str | None]:
    resolved_prefix = conda.get("resolved_prefix")
    if not resolved_prefix:
        return None, None
    candidate = Path(resolved_prefix) / "bin" / command
    if _safe_exists(candidate):
        if conda.get("requested_mode") == "active_env":
            return str(candidate), "active_conda_env"
        return str(candidate), "conda_prefix"
    return None, None


def probe_tools(conda: dict[str, Any] | None = None, warnings: list[str] | None = None) -> dict[str, dict[str, Any]]:
    conda = conda or {}
    warnings = warnings if warnings is not None else []
    tools: dict[str, dict[str, Any]] = {}
    conda_resolved = conda.get("status") == "detected"

    for key, command in TOOL_COMMANDS.items():
        conda_path, conda_source = _conda_tool_path(conda, command)
        if conda_path is not None:
            tools[key] = probe_item(
                "detected",
                path=conda_path,
                version_text=capture_version_text(conda_path),
                source=conda_source,
                from_conda=True,
            )
            continue

        resolved = shutil.which(command)
        if resolved is None:
            tools[key] = probe_item("missing", path=None, version_text=None, source="missing", from_conda=False)
            continue

        tools[key] = probe_item(
            "detected",
            path=resolved,
            version_text=capture_version_text(resolved),
            source="path",
            from_conda=False,
        )
        if conda_resolved:
            warnings.append(
                f"Tool `{command}` was not found inside the resolved Conda environment and fell back to PATH: {resolved}"
            )

    return tools


def _safe_exists(path: str | Path) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if _safe_exists(path):
            return path
    return None


def path_exists(path: str | Path) -> bool:
    return _safe_exists(path)


def load_conda_env_prefixes() -> list[str] | None:
    try:
        completed = subprocess.run(
            ["conda", "env", "list", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return [str(Path(item)) for item in payload.get("envs", [])]


def _match_conda_name(prefixes: list[str], name: str) -> str | None:
    for prefix in prefixes:
        if Path(prefix).name == name:
            return prefix
    if name != "base":
        return None

    normalized = [(prefix, prefix.replace("\\", "/").rstrip("/")) for prefix in prefixes]
    root_candidates: list[str] = []
    for prefix, normalized_prefix in normalized:
        nested_prefix = f"{normalized_prefix}/envs/"
        if any(other.startswith(nested_prefix) for _, other in normalized if other != normalized_prefix):
            root_candidates.append(prefix)

    if len(root_candidates) == 1:
        return root_candidates[0]
    if len(prefixes) == 1:
        return prefixes[0]
    return None


def resolve_conda_target(args: argparse.Namespace) -> dict[str, Any]:
    active_prefix = os.environ.get("CONDA_PREFIX")
    active_env_name = os.environ.get("CONDA_DEFAULT_ENV")
    info = {
        "requested_mode": "none",
        "requested_name": None,
        "requested_prefix": None,
        "resolved_prefix": None,
        "active_prefix": active_prefix,
        "active_env_name": active_env_name,
        "status": "manual",
        "notes": [],
    }

    if args.conda_prefix:
        info["requested_mode"] = "prefix"
        info["requested_prefix"] = args.conda_prefix
        if path_exists(args.conda_prefix):
            info["resolved_prefix"] = args.conda_prefix
            info["status"] = "detected"
        else:
            info["status"] = "missing"
            info["notes"].append(f"Requested conda prefix was not found: {args.conda_prefix}")
        return info

    if args.conda_name:
        info["requested_mode"] = "name"
        info["requested_name"] = args.conda_name
        prefixes = load_conda_env_prefixes()
        if prefixes is None:
            info["status"] = "missing"
            info["notes"].append("Could not resolve conda name because `conda env list --json` was unavailable.")
            return info
        if active_env_name == args.conda_name and active_prefix:
            matched = active_prefix
        else:
            matched = _match_conda_name(prefixes, args.conda_name)
        if matched is None:
            info["status"] = "missing"
            info["notes"].append(f"Requested conda env name was not found: {args.conda_name}")
            return info
        info["resolved_prefix"] = matched
        info["status"] = "detected"
        return info

    if active_prefix:
        info["requested_mode"] = "active_env"
        info["resolved_prefix"] = active_prefix
        info["status"] = "detected"
        return info

    return info


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


def collect_probe_report(args: argparse.Namespace) -> dict[str, Any]:
    report = build_initial_report()
    conda = resolve_conda_target(args)
    report["conda"] = conda
    report["warnings"].extend(conda["notes"])
    report["tools"] = probe_tools(conda, report["warnings"])
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
        f"conda request: {report['conda']['requested_mode']}",
        f"conda resolved prefix: {report['conda']['resolved_prefix']}",
    ]
    for tool_name, tool_data in sorted(report["tools"].items()):
        lines.append(f"{tool_name} source: {tool_data.get('source', tool_data.get('status'))}")
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
    report = collect_probe_report(args)
    write_probe_bundle(Path(args.output_dir), report)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe a thermo-mining server before repo clone.")
    parser.add_argument("--output-dir", default="thermo_server_probe")
    parser.add_argument("--conda-prefix", default=None)
    parser.add_argument("--conda-name", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
