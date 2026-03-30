# Thermo Mining Server Probe Conda Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the standalone server probe so it can resolve a Conda environment by explicit prefix, explicit name, or currently active env and record whether detected tools came from Conda or non-Conda sources.

**Architecture:** Keep the probe as a single standard-library-only script at `scripts/server_probe.py`, but add focused helper functions for Conda resolution, Conda-aware tool lookup, and summary rendering. Tests continue to load the script by file path via `importlib`, and the YAML output remains config-shaped while Conda-specific metadata stays in `server_probe.json` and `server_probe.txt`.

**Tech Stack:** Python 3.11+, pytest, importlib.util, argparse, pathlib, subprocess, json, shutil

---

## File Map

- `scripts/server_probe.py`
  - Add Conda CLI flags, Conda resolution helpers, Conda-aware tool probing, and Conda metadata rendering
- `tests/test_server_probe.py`
  - Add TDD coverage for Conda args, Conda target resolution, Conda-aware tool selection, warnings, and output rendering
- `README.md`
  - Document the new `--conda-prefix` and `--conda-name` workflows

### Task 1: Add Conda CLI Flags And Report Skeleton

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_probe.py::test_parse_args_accepts_conda_prefix_and_name tests/test_server_probe.py::test_build_initial_report_includes_manual_conda_section -v`
Expected: FAIL because `parse_args()` does not accept the Conda flags and `build_initial_report()` has no `conda` section yet

- [ ] **Step 3: Write minimal implementation**

```python
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe a thermo-mining server before repo clone.")
    parser.add_argument("--output-dir", default="thermo_server_probe")
    parser.add_argument("--conda-prefix", default=None)
    parser.add_argument("--conda-name", default=None)
    return parser.parse_args(argv)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_probe.py::test_parse_args_accepts_conda_prefix_and_name tests/test_server_probe.py::test_build_initial_report_includes_manual_conda_section -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): add conda cli metadata"
```

### Task 2: Resolve Explicit Prefix, Explicit Name, And Active Conda Env

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_probe.py::test_resolve_conda_target_prefers_explicit_prefix tests/test_server_probe.py::test_resolve_conda_target_resolves_name_and_uses_active_env_fallback -v`
Expected: FAIL because `path_exists`, `load_conda_env_prefixes`, and `resolve_conda_target` do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
def path_exists(path: str | Path) -> bool:
    return Path(path).exists()


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_probe.py::test_resolve_conda_target_prefers_explicit_prefix tests/test_server_probe.py::test_resolve_conda_target_resolves_name_and_uses_active_env_fallback -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): resolve conda targets"
```

### Task 3: Make Tool Detection Conda-Aware And Warn On Fallback

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`

- [ ] **Step 1: Write the failing tests**

```python
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

    monkeypatch.setattr(probe.shutil, "which", lambda name: f"/usr/bin/{name}")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_probe.py::test_probe_tools_prefers_resolved_conda_prefix tests/test_server_probe.py::test_probe_tools_warns_when_tool_falls_back_outside_conda -v`
Expected: FAIL because `probe_tools()` does not accept Conda metadata and does not record `source` or `from_conda`

- [ ] **Step 3: Write minimal implementation**

```python
def _conda_tool_path(conda: dict[str, Any], command: str) -> tuple[str | None, str | None]:
    resolved_prefix = conda.get("resolved_prefix")
    if not resolved_prefix:
        return None, None
    candidate = Path(resolved_prefix) / "bin" / command
    if candidate.exists():
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_probe.py::test_probe_tools_prefers_resolved_conda_prefix tests/test_server_probe.py::test_probe_tools_warns_when_tool_falls_back_outside_conda -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/server_probe.py tests/test_server_probe.py
git commit -m "feat(server-probe): prefer conda tool paths"
```

### Task 4: Render Conda Metadata In JSON And Summary Output

**Files:**
- Modify: `scripts/server_probe.py`
- Modify: `tests/test_server_probe.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_probe.py::test_main_writes_conda_metadata_and_summary_lines -v`
Expected: FAIL because `collect_probe_report()` does not accept parsed args and the summary output does not include Conda metadata yet

- [ ] **Step 3: Write minimal implementation**

```python
def collect_probe_report(args: argparse.Namespace) -> dict[str, Any]:
    report = build_initial_report()
    conda = resolve_conda_target(args)
    report["conda"] = conda
    report["warnings"].extend(conda["notes"])
    report["tools"] = probe_tools(conda, report["warnings"])
    add_candidate_sections(report)
    return report


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
        lines.append(f"{tool_name} source: {tool_data['source']}")
    if report["warnings"]:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = collect_probe_report(args)
    write_probe_bundle(Path(args.output_dir), report)
    return 0
```

```markdown
## Server Probe

Run the standalone probe on the target Linux server:

```bash
python3 scripts/server_probe.py --output-dir ./thermo_server_probe
python3 scripts/server_probe.py --output-dir ./thermo_server_probe --conda-prefix /abs/path/to/env
python3 scripts/server_probe.py --output-dir ./thermo_server_probe --conda-name thermo
```

If a resolved Conda env does not contain a tool but the normal system `PATH`
does, the probe records the PATH result and emits a warning instead of failing.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_probe.py::test_main_writes_conda_metadata_and_summary_lines -v`
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
git commit -m "feat(server-probe): report conda probe metadata"
```

## Self-Review

### Spec coverage

- support `--conda-prefix` and `--conda-name`: Task 1 and Task 2
- fixed priority of prefix > name > active env > non-Conda fallback: Task 2
- `conda env list --json` resolution for env name: Task 2
- `conda` metadata block in `server_probe.json`: Task 1 and Task 4
- tool `source` and `from_conda` fields: Task 3 and Task 4
- mixed-source warning behavior when Conda resolves but PATH wins: Task 3
- no new `conda:` top-level YAML section: Task 4
- summary text includes Conda request and source lines: Task 4
- keep fallback behavior and exit semantics intact: Task 2, Task 3, and Task 4

No Conda-support requirement from the approved extension spec is left without a task.

### Placeholder scan

There are no `TBD`, `TODO`, `implement later`, or cross-task "same as above"
placeholders in this plan. Each code step includes concrete tests, concrete
implementation code, and exact commands.

### Type consistency

- The `conda` report keys remain `requested_mode`, `requested_name`,
  `requested_prefix`, `resolved_prefix`, `active_prefix`, `active_env_name`,
  `status`, and `notes` throughout the plan
- Tool metadata consistently uses `source` and `from_conda`
- CLI flags remain exactly `--conda-prefix` and `--conda-name`
- `collect_probe_report(args)` is the only final signature used after Conda
  support is introduced
