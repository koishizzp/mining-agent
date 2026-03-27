# Thermo Mining Control Plane MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-user control-plane MVP for thermo mining that adds chat-driven planning, server-side path browsing, plan review, tmux-backed execution, run monitoring, artifact browsing, and a restricted OpenAI-compatible chat API around the existing pipeline.

**Architecture:** Keep the control plane as a thin FastAPI application layered on top of the existing pipeline stages. The new code is split into focused control-plane modules for schemas, filesystem services, planning, run persistence, job management, and web/API delivery, while the runner orchestrates bundle-specific DAGs and writes `runtime_state.json` as the single source of truth.

**Tech Stack:** Python 3.11, pytest, pydantic, FastAPI, Jinja2, uvicorn, OpenAI SDK, HTMX-lite via fetch/original JS, tmux, subprocess

---

## File Map

- `pyproject.toml`
  - Add `jinja2` and package data for templates/static assets
- `README.md`
  - Document control-plane setup, commands, and deployment model
- `config/platform.example.yaml`
  - Extend control-plane runtime and tool settings, including `tmux_bin`
- `src/thermo_mining/settings.py`
  - Central typed settings for web service, runs root, LLM, and `tmux`
- `src/thermo_mining/cli.py`
  - Add `serve` and `run-job` commands
- `src/thermo_mining/control_plane/__init__.py`
  - Control-plane package marker
- `src/thermo_mining/control_plane/schemas.py`
  - Pydantic models for path entries, bundles, plans, runs, stage state, and artifacts
- `src/thermo_mining/control_plane/stage_graph.py`
  - Bundle-type DAG selection and editable plan field definitions
- `src/thermo_mining/control_plane/fs_service.py`
  - Absolute-path normalization, listing, and search
- `src/thermo_mining/control_plane/fastq_pairing.py`
  - FASTQ pairing and bundle scanning
- `src/thermo_mining/control_plane/run_store.py`
  - Run directory creation, runtime state I/O, active-run lock, and artifact indexing
- `src/thermo_mining/control_plane/upstream_steps.py`
  - `fastp`, `SPAdes`, and `Prodigal` adapters
- `src/thermo_mining/control_plane/runner.py`
  - Bundle-aware execution orchestrator for `paired_fastq`, `contigs`, and `proteins`
- `src/thermo_mining/control_plane/job_manager.py`
  - `tmux` command building and run lifecycle control
- `src/thermo_mining/control_plane/llm_client.py`
  - Thin OpenAI-compatible JSON planning client
- `src/thermo_mining/control_plane/planner.py`
  - Plan generation, limited review edits, and fallback parsing
- `src/thermo_mining/control_plane/status_explainer.py`
  - Current-run and failure explanation helpers
- `src/thermo_mining/web/__init__.py`
  - Web package marker
- `src/thermo_mining/web/dependencies.py`
  - Shared dependency builders for settings, planner, job manager, and run store
- `src/thermo_mining/web/routes_pages.py`
  - HTML route for the single-page console
- `src/thermo_mining/web/routes_api_fs.py`
  - Filesystem JSON endpoints
- `src/thermo_mining/web/routes_api_plan.py`
  - Planning JSON endpoint
- `src/thermo_mining/web/routes_api_runs.py`
  - Run lifecycle, monitoring, logs, and artifact JSON endpoints
- `src/thermo_mining/web/routes_api_chat.py`
  - Restricted `POST /v1/chat/completions`
- `src/thermo_mining/web/app.py`
  - FastAPI app factory and router registration
- `src/thermo_mining/web/templates/index.html`
  - Single-page console shell
- `src/thermo_mining/web/static/console.js`
  - Minimal front-end state and polling logic
- `src/thermo_mining/web/static/console.css`
  - Simple layout and console styling
- `scripts/start_web.sh`
  - Start FastAPI/uvicorn service with logging
- `scripts/start_all.sh`
  - Alias for the on-demand worker model plus preflight checks
- `scripts/status.sh`
  - Service and active-run status
- `scripts/stop.sh`
  - Stop web service and report any active tmux run
- `tests/test_control_plane_bootstrap.py`
  - Settings and CLI bootstrap tests
- `tests/control_plane/test_schemas.py`
  - Schema and stage graph tests
- `tests/control_plane/test_fs_service.py`
  - Filesystem service tests
- `tests/control_plane/test_fastq_pairing.py`
  - Pairing and bundle scanning tests
- `tests/control_plane/test_run_store.py`
  - Run directory and runtime state tests
- `tests/control_plane/test_upstream_steps.py`
  - Adapter command tests
- `tests/control_plane/test_runner.py`
  - Bundle-aware runner tests
- `tests/control_plane/test_job_manager.py`
  - `tmux` lifecycle tests
- `tests/control_plane/test_planner.py`
  - Planner, fallback, and failure explanation tests
- `tests/web/test_fs_and_plan_api.py`
  - Filesystem and plan endpoint tests
- `tests/web/test_runs_and_chat_api.py`
  - Run lifecycle and OpenAI-compatible chat endpoint tests
- `tests/web/test_pages.py`
  - Console HTML route tests

### Task 1: Bootstrap Control Plane Settings And CLI Commands

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/platform.example.yaml`
- Modify: `src/thermo_mining/settings.py`
- Modify: `src/thermo_mining/cli.py`
- Create: `tests/test_control_plane_bootstrap.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_control_plane_bootstrap.py -v`
Expected: FAIL because `serve` / `run-job` are not recognized and `tmux_bin` is missing from settings

- [ ] **Step 3: Write minimal implementation**

```toml
[project]
dependencies = [
  "PyYAML>=6.0,<7",
  "requests>=2.32,<3",
  "pydantic>=2.9,<3",
  "fastapi>=0.115,<1",
  "uvicorn>=0.32,<1",
  "openai>=1.54,<2",
  "httpx>=0.28,<1",
  "jinja2>=3.1,<4",
]

[tool.setuptools.package-data]
"thermo_mining.web" = ["templates/*.html", "static/*.js", "static/*.css"]
```

```yaml
tools:
  fastp_bin: /usr/bin/fastp
  spades_bin: /usr/bin/spades.py
  prodigal_bin: /usr/bin/prodigal
  mmseqs_bin: /usr/bin/mmseqs
  temstapro_bin: /opt/temstapro/bin/temstapro
  protrek_python_bin: /opt/protrek/bin/python
  protrek_repo_root: /srv/ProTrek
  protrek_weights_dir: /srv/ProTrek/weights/ProTrek_650M
  foldseek_base_url: http://127.0.0.1:8100
  tmux_bin: /usr/bin/tmux
```

```python
@dataclass(frozen=True)
class ToolSettings:
    fastp_bin: str = "fastp"
    spades_bin: str = "spades.py"
    prodigal_bin: str = "prodigal"
    mmseqs_bin: str = "mmseqs"
    temstapro_bin: str = "temstapro"
    protrek_python_bin: str = "python"
    protrek_repo_root: Path = Path("/srv/ProTrek")
    protrek_weights_dir: Path = Path("/srv/ProTrek/weights/ProTrek_650M")
    foldseek_base_url: str = "http://127.0.0.1:8100"
    tmux_bin: str = "tmux"
```

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thermo-mining")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--run-name", required=True)
    run_parser.add_argument("--input-faa", required=True)
    run_parser.add_argument("--resume", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.add_argument("--config", default="config/platform.example.yaml")

    run_job_parser = subparsers.add_parser("run-job")
    run_job_parser.add_argument("--run-dir", required=True)
    run_job_parser.add_argument("--config", default="config/platform.example.yaml")
    return parser
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_control_plane_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml config/platform.example.yaml src/thermo_mining/settings.py src/thermo_mining/cli.py tests/test_control_plane_bootstrap.py
git commit -m "build(control-plane): bootstrap settings and cli"
```

### Task 2: Add Pydantic Schemas And Bundle-Type Stage Graphs

**Files:**
- Create: `src/thermo_mining/control_plane/__init__.py`
- Create: `src/thermo_mining/control_plane/schemas.py`
- Create: `src/thermo_mining/control_plane/stage_graph.py`
- Create: `tests/control_plane/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle, REVIEW_EDITABLE_FIELDS
from thermo_mining.control_plane.stage_graph import build_stage_order


def test_input_bundle_requires_absolute_paths():
    with pytest.raises(ValidationError):
        InputBundle(
            bundle_type="proteins",
            sample_id="S01",
            input_paths=["inputs/S01.faa"],
            metadata={},
            output_root="/runs/S01",
        )


def test_execution_plan_defaults_to_confirmation():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )

    plan = ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="Run the default proteins flow",
    )

    assert plan.requires_confirmation is True
    assert "output_root" in REVIEW_EDITABLE_FIELDS


def test_build_stage_order_for_all_bundle_types():
    assert build_stage_order("paired_fastq") == [
        "fastp",
        "spades",
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ]
    assert build_stage_order("contigs")[0] == "prodigal"
    assert build_stage_order("proteins")[0] == "prefilter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError` for `thermo_mining.control_plane`

- [ ] **Step 3: Write minimal implementation**

```python
"""Control-plane services for the thermo mining platform."""
```

```python
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


BundleType = Literal["paired_fastq", "contigs", "proteins"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "stopped"]

REVIEW_EDITABLE_FIELDS = {
    "output_root",
    "resume_policy",
    "prefilter_min_length",
    "prefilter_max_length",
    "prefilter_max_single_residue_fraction",
    "thermo_top_fraction",
    "thermo_min_score",
    "protrek_top_k",
    "foldseek_topk",
    "foldseek_min_tmscore",
}


class InputBundle(BaseModel):
    bundle_type: BundleType
    sample_id: str
    input_paths: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_root: str

    @field_validator("input_paths")
    @classmethod
    def validate_absolute_paths(cls, value: list[str]) -> list[str]:
        for item in value:
            if not item.startswith("/"):
                raise ValueError("input paths must be absolute")
        return value


class ExecutionPlan(BaseModel):
    bundle_type: BundleType
    input_items: list[InputBundle]
    stage_order: list[str]
    parameter_overrides: dict[str, Any]
    output_root: str
    resume_policy: Literal["never", "if_possible"]
    requires_confirmation: bool = True
    explanation: str


class PathEntry(BaseModel):
    path: str
    name: str
    kind: Literal["file", "dir"]
    size: int
    mtime: float
    is_symlink: bool = False


class FastqPairCandidate(BaseModel):
    sample_id: str
    read1: str
    read2: str
    confidence: float
    needs_manual_confirmation: bool = False


class StageState(BaseModel):
    stage_name: str
    status: RunStatus
    input_hash: str = ""
    parameter_digest: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error_summary: str | None = None


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    created_at: str
    confirmed_at: str | None = None
    tmux_session: str | None = None
    run_dir: str


class ArtifactEntry(BaseModel):
    kind: str
    path: str
    label: str
    size: int
    updated_at: float
```

```python
from .schemas import BundleType


STAGE_ORDERS: dict[BundleType, list[str]] = {
    "paired_fastq": [
        "fastp",
        "spades",
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
    "contigs": [
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
    "proteins": [
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
}


def build_stage_order(bundle_type: BundleType) -> list[str]:
    return STAGE_ORDERS[bundle_type]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/__init__.py src/thermo_mining/control_plane/schemas.py src/thermo_mining/control_plane/stage_graph.py tests/control_plane/test_schemas.py
git commit -m "feat(control-plane): add schemas and stage graph"
```

### Task 3: Implement Absolute-Path Filesystem Listing And Search

**Files:**
- Create: `src/thermo_mining/control_plane/fs_service.py`
- Create: `tests/control_plane/test_fs_service.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from thermo_mining.control_plane.fs_service import list_path_entries, normalize_absolute_path, search_path_entries


def test_normalize_absolute_path_rejects_relative_paths(tmp_path):
    with pytest.raises(ValueError):
        normalize_absolute_path("relative/path.txt")


def test_list_path_entries_returns_sorted_children(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    rows = list_path_entries(tmp_path)

    assert [row.name for row in rows] == ["a.txt", "b.txt"]
    assert rows[0].kind == "file"


def test_search_path_entries_finds_nested_matches(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hot_spring_reads_1.fq.gz").write_text("x", encoding="utf-8")

    rows = search_path_entries(tmp_path, "hot_spring")

    assert rows[0].path.endswith("hot_spring_reads_1.fq.gz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_fs_service.py -v`
Expected: FAIL with `ModuleNotFoundError` for `fs_service`

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path

from .schemas import PathEntry


def normalize_absolute_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError("path must be absolute")
    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    return resolved


def _to_path_entry(path: Path) -> PathEntry:
    stat = path.stat()
    return PathEntry(
        path=str(path),
        name=path.name,
        kind="dir" if path.is_dir() else "file",
        size=stat.st_size,
        mtime=stat.st_mtime,
        is_symlink=path.is_symlink(),
    )


def list_path_entries(path: str | Path) -> list[PathEntry]:
    root = normalize_absolute_path(path)
    if not root.is_dir():
        raise ValueError("path must be a directory")
    return [_to_path_entry(child) for child in sorted(root.iterdir(), key=lambda item: item.name.lower())]


def search_path_entries(root: str | Path, query: str, limit: int = 50) -> list[PathEntry]:
    base = normalize_absolute_path(root)
    matches: list[PathEntry] = []
    for candidate in base.rglob("*"):
        if query.lower() in candidate.name.lower():
            matches.append(_to_path_entry(candidate))
        if len(matches) >= limit:
            break
    return matches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_fs_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/fs_service.py tests/control_plane/test_fs_service.py
git commit -m "feat(control-plane): add filesystem listing and search"
```

### Task 4: Add FASTQ Pairing And Bundle Scanning

**Files:**
- Create: `src/thermo_mining/control_plane/fastq_pairing.py`
- Create: `tests/control_plane/test_fastq_pairing.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.control_plane.fastq_pairing import detect_fastq_pairs, scan_input_bundles


def test_detect_fastq_pairs_matches_common_r1_r2_patterns(tmp_path):
    read1 = tmp_path / "sample_R1.fastq.gz"
    read2 = tmp_path / "sample_R2.fastq.gz"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    pairs = detect_fastq_pairs([read1, read2])

    assert pairs[0].sample_id == "sample"
    assert pairs[0].read1.endswith("sample_R1.fastq.gz")
    assert pairs[0].read2.endswith("sample_R2.fastq.gz")


def test_scan_input_bundles_detects_proteins_and_contigs(tmp_path):
    proteins = tmp_path / "S01.faa"
    contigs = tmp_path / "S02_contigs.fa"
    proteins.write_text(">p1\nAAAA\n", encoding="utf-8")
    contigs.write_text(">c1\nATGC\n", encoding="utf-8")

    bundles = scan_input_bundles(tmp_path, output_root=tmp_path / "runs")

    assert {bundle.bundle_type for bundle in bundles} == {"proteins", "contigs"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_fastq_pairing.py -v`
Expected: FAIL with `ModuleNotFoundError` for `fastq_pairing`

- [ ] **Step 3: Write minimal implementation**

```python
import re
from pathlib import Path

from .schemas import FastqPairCandidate, InputBundle


PAIR_PATTERNS = [
    (re.compile(r"(.+)_R1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "_R2"),
    (re.compile(r"(.+)_1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "_2"),
    (re.compile(r"(.+)\.1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), ".2"),
]


def detect_fastq_pairs(paths: list[Path]) -> list[FastqPairCandidate]:
    index = {path.name: path for path in paths}
    pairs: list[FastqPairCandidate] = []
    for path in paths:
        for pattern, partner_marker in PAIR_PATTERNS:
            match = pattern.match(path.name)
            if not match:
                continue
            sample_id = match.group(1)
            partner_name = path.name.replace(partner_marker.replace("2", "1"), partner_marker)
            partner = index.get(partner_name)
            if partner is None:
                continue
            if "_R1" in path.name or path.name.endswith("_1.fastq.gz") or ".1.fastq.gz" in path.name:
                pairs.append(
                    FastqPairCandidate(
                        sample_id=sample_id,
                        read1=str(path.resolve()),
                        read2=str(partner.resolve()),
                        confidence=1.0,
                        needs_manual_confirmation=False,
                    )
                )
            break
    unique = {(pair.sample_id, pair.read1, pair.read2): pair for pair in pairs}
    return list(unique.values())


def scan_input_bundles(root: str | Path, output_root: str | Path) -> list[InputBundle]:
    root = Path(root).resolve()
    output_root = Path(output_root).resolve()
    paths = [path for path in root.iterdir() if path.is_file()]
    bundles: list[InputBundle] = []

    for pair in detect_fastq_pairs(paths):
        bundles.append(
            InputBundle(
                bundle_type="paired_fastq",
                sample_id=pair.sample_id,
                input_paths=[pair.read1, pair.read2],
                metadata={},
                output_root=str(output_root / pair.sample_id),
            )
        )

    for path in paths:
        suffixes = "".join(path.suffixes).lower()
        if suffixes.endswith((".faa", ".faa.gz")):
            bundles.append(
                InputBundle(
                    bundle_type="proteins",
                    sample_id=path.stem,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / path.stem),
                )
            )
        if suffixes.endswith((".fa", ".fasta", ".fa.gz", ".fasta.gz")) and "contig" in path.stem.lower():
            bundles.append(
                InputBundle(
                    bundle_type="contigs",
                    sample_id=path.stem,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / path.stem),
                )
            )
    return bundles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_fastq_pairing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/fastq_pairing.py tests/control_plane/test_fastq_pairing.py
git commit -m "feat(control-plane): add fastq pairing and bundle scanning"
```

### Task 5: Persist Pending Runs, Runtime State, And Artifact Listings

**Files:**
- Create: `src/thermo_mining/control_plane/run_store.py`
- Create: `tests/control_plane/test_run_store.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.control_plane.run_store import clear_active_run, create_pending_run, read_active_run, read_runtime_state, set_active_run
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _build_plan() -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    return ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="test plan",
    )


def test_create_pending_run_writes_run_layout(tmp_path):
    record = create_pending_run(tmp_path, _build_plan())

    run_dir = tmp_path / record.run_id
    assert (run_dir / "execution_plan.json").exists()
    assert (run_dir / "runtime_state.json").exists()
    assert read_runtime_state(run_dir).status == "pending"


def test_active_run_lock_roundtrip(tmp_path):
    set_active_run(tmp_path, "run_001")
    assert read_active_run(tmp_path) == "run_001"
    clear_active_run(tmp_path)
    assert read_active_run(tmp_path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_run_store.py -v`
Expected: FAIL with `ModuleNotFoundError` for `run_store`

- [ ] **Step 3: Write minimal implementation**

```python
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .schemas import ArtifactEntry, ExecutionPlan, RunRecord


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_pending_run(runs_root: str | Path, plan: ExecutionPlan) -> RunRecord:
    runs_root = Path(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = f"run_{uuid4().hex[:8]}"
    run_dir = runs_root / run_id
    (run_dir / "stage_logs").mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "reports").mkdir()

    record = RunRecord(run_id=run_id, status="pending", created_at=_now_iso(), run_dir=str(run_dir))
    (run_dir / "execution_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "bundle_manifest.json").write_text(
        json.dumps([item.model_dump() for item in plan.input_items], indent=2),
        encoding="utf-8",
    )
    write_runtime_state(run_dir, {"run_id": run_id, "status": "pending", "active_stage": None, "stages": []})
    return record


def write_runtime_state(run_dir: str | Path, payload: dict[str, object]) -> None:
    Path(run_dir, "runtime_state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_runtime_state(run_dir: str | Path) -> RunRecord:
    payload = json.loads(Path(run_dir, "runtime_state.json").read_text(encoding="utf-8"))
    return RunRecord(
        run_id=payload["run_id"],
        status=payload["status"],
        created_at=payload.get("created_at", ""),
        confirmed_at=payload.get("confirmed_at"),
        tmux_session=payload.get("tmux_session"),
        run_dir=str(Path(run_dir)),
    )


def set_active_run(runs_root: str | Path, run_id: str) -> None:
    control_dir = Path(runs_root) / "_control_plane"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "active_run.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")


def read_active_run(runs_root: str | Path) -> str | None:
    marker = Path(runs_root) / "_control_plane" / "active_run.json"
    if not marker.exists():
        return None
    return json.loads(marker.read_text(encoding="utf-8"))["run_id"]


def clear_active_run(runs_root: str | Path) -> None:
    marker = Path(runs_root) / "_control_plane" / "active_run.json"
    if marker.exists():
        marker.unlink()


def list_artifacts(run_dir: str | Path) -> list[ArtifactEntry]:
    base = Path(run_dir)
    roots = [base / "artifacts", base / "reports"]
    rows: list[ArtifactEntry] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                stat = path.stat()
                rows.append(
                    ArtifactEntry(
                        kind=path.suffix.lstrip(".") or "file",
                        path=str(path),
                        label=path.name,
                        size=stat.st_size,
                        updated_at=stat.st_mtime,
                    )
                )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_run_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/run_store.py tests/control_plane/test_run_store.py
git commit -m "feat(control-plane): persist run state and artifacts"
```

### Task 6: Add Fastp, SPAdes, And Prodigal Adapter Commands

**Files:**
- Create: `src/thermo_mining/control_plane/upstream_steps.py`
- Create: `tests/control_plane/test_upstream_steps.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.control_plane.upstream_steps import (
    build_fastp_command,
    build_prodigal_command,
    build_spades_command,
)


def test_build_fastp_command_includes_input_and_output_paths(tmp_path):
    cmd = build_fastp_command(
        fastp_bin="fastp",
        read1=tmp_path / "sample_1.fq.gz",
        read2=tmp_path / "sample_2.fq.gz",
        out_read1=tmp_path / "clean_1.fq.gz",
        out_read2=tmp_path / "clean_2.fq.gz",
        html_report=tmp_path / "fastp.html",
        json_report=tmp_path / "fastp.json",
    )

    assert cmd[:2] == ["fastp", "-i"]
    assert str(tmp_path / "clean_1.fq.gz") in cmd


def test_build_spades_and_prodigal_commands_use_expected_flags(tmp_path):
    spades_cmd = build_spades_command(
        spades_bin="spades.py",
        read1=tmp_path / "clean_1.fq.gz",
        read2=tmp_path / "clean_2.fq.gz",
        output_dir=tmp_path / "spades",
        threads=32,
    )
    prodigal_cmd = build_prodigal_command(
        prodigal_bin="prodigal",
        contigs_fa=tmp_path / "contigs.fasta",
        proteins_faa=tmp_path / "proteins.faa",
        genes_fna=tmp_path / "genes.fna",
    )

    assert "--threads" in spades_cmd
    assert "-a" in prodigal_cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_upstream_steps.py -v`
Expected: FAIL with `ModuleNotFoundError` for `upstream_steps`

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path
import subprocess


def build_fastp_command(
    fastp_bin: str,
    read1: str | Path,
    read2: str | Path,
    out_read1: str | Path,
    out_read2: str | Path,
    html_report: str | Path,
    json_report: str | Path,
) -> list[str]:
    return [
        fastp_bin,
        "-i",
        str(read1),
        "-I",
        str(read2),
        "-o",
        str(out_read1),
        "-O",
        str(out_read2),
        "--html",
        str(html_report),
        "--json",
        str(json_report),
    ]


def build_spades_command(
    spades_bin: str,
    read1: str | Path,
    read2: str | Path,
    output_dir: str | Path,
    threads: int,
) -> list[str]:
    return [
        spades_bin,
        "-1",
        str(read1),
        "-2",
        str(read2),
        "-o",
        str(output_dir),
        "--threads",
        str(threads),
    ]


def build_prodigal_command(
    prodigal_bin: str,
    contigs_fa: str | Path,
    proteins_faa: str | Path,
    genes_fna: str | Path,
) -> list[str]:
    return [
        prodigal_bin,
        "-i",
        str(contigs_fa),
        "-a",
        str(proteins_faa),
        "-d",
        str(genes_fna),
        "-p",
        "meta",
    ]


def run_fastp_stage(
    read1: str | Path,
    read2: str | Path,
    stage_dir: str | Path,
    fastp_bin: str,
) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    out_read1 = stage_dir / "clean_R1.fastq.gz"
    out_read2 = stage_dir / "clean_R2.fastq.gz"
    cmd = build_fastp_command(
        fastp_bin=fastp_bin,
        read1=read1,
        read2=read2,
        out_read1=out_read1,
        out_read2=out_read2,
        html_report=stage_dir / "fastp.html",
        json_report=stage_dir / "fastp.json",
    )
    subprocess.run(cmd, check=True)
    return {"read1": out_read1, "read2": out_read2}


def run_spades_stage(
    read1: str | Path,
    read2: str | Path,
    stage_dir: str | Path,
    spades_bin: str,
    threads: int,
) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_spades_command(spades_bin, read1, read2, stage_dir, threads)
    subprocess.run(cmd, check=True)
    return {"contigs_fa": stage_dir / "contigs.fasta"}


def run_prodigal_stage(
    contigs_fa: str | Path,
    stage_dir: str | Path,
    prodigal_bin: str = "prodigal",
    software_version: str = "0.1.0",
) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    proteins_faa = stage_dir / "proteins.faa"
    genes_fna = stage_dir / "genes.fna"
    cmd = build_prodigal_command(prodigal_bin, contigs_fa, proteins_faa, genes_fna)
    subprocess.run(cmd, check=True)
    return {"proteins_faa": proteins_faa, "genes_fna": genes_fna}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_upstream_steps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/upstream_steps.py tests/control_plane/test_upstream_steps.py
git commit -m "feat(control-plane): add upstream adapter commands"
```

### Task 7: Implement The Bundle-Aware Runner

**Files:**
- Create: `src/thermo_mining/control_plane/runner.py`
- Create: `tests/control_plane/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from thermo_mining.control_plane.run_store import create_pending_run
from thermo_mining.control_plane.runner import run_job
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _make_plan(bundle_type: str, input_paths: list[str], output_root: str) -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type=bundle_type,
        sample_id="S01",
        input_paths=input_paths,
        metadata={},
        output_root=output_root,
    )
    return ExecutionPlan(
        bundle_type=bundle_type,
        input_items=[bundle],
        stage_order=build_stage_order(bundle_type),
        parameter_overrides={},
        output_root=output_root,
        resume_policy="if_possible",
        explanation="test",
    )


def test_run_job_executes_expected_stage_order_for_contigs(tmp_path, monkeypatch):
    plan = _make_plan("contigs", ["/mnt/disk2/S01_contigs.fa"], "/runs/S01")
    record = create_pending_run(tmp_path, plan)
    calls: list[str] = []

    monkeypatch.setattr("thermo_mining.control_plane.runner.run_prodigal_stage", lambda **kwargs: calls.append("prodigal") or {"proteins_faa": tmp_path / "proteins.faa"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_prefilter", lambda **kwargs: calls.append("prefilter") or {"filtered_faa": tmp_path / "filtered.faa"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_mmseqs_cluster", lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": tmp_path / "cluster.faa"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_temstapro_screen", lambda **kwargs: calls.append("temstapro") or {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_protrek_stage", lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_foldseek_stage", lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.write_report_outputs", lambda *args, **kwargs: calls.append("report") or {"summary_md": tmp_path / "summary.md"})
    monkeypatch.setattr("thermo_mining.control_plane.runner.combine_stage_scores", lambda **kwargs: [{"protein_id": "p1", "tier": "Tier 1", "final_score": 0.9, "thermo_score": 0.9, "protrek_score": 0.9, "foldseek_score": 0.9, "origin_bonus": 0.0}])
    monkeypatch.setattr("thermo_mining.control_plane.runner._read_scores_tsv", lambda path: [{"protein_id": "p1", "thermo_score": "0.9", "protrek_score": "0.9", "foldseek_score": "0.9"}])

    run_job(record.run_dir)

    state = json.loads((tmp_path / record.run_id / "runtime_state.json").read_text(encoding="utf-8"))
    assert calls == ["prodigal", "prefilter", "mmseqs", "temstapro", "protrek", "foldseek", "report"]
    assert state["status"] == "succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError` for `runner`

- [ ] **Step 3: Write minimal implementation**

```python
import json
from datetime import UTC, datetime
from pathlib import Path

from thermo_mining import __version__
from thermo_mining.control_plane.run_store import write_runtime_state
from thermo_mining.control_plane.upstream_steps import run_fastp_stage, run_prodigal_stage, run_spades_stage
from thermo_mining.pipeline import _read_scores_tsv
from thermo_mining.reporting import write_report_outputs
from thermo_mining.steps.foldseek_client import run_foldseek_stage
from thermo_mining.steps.mmseqs_cluster import run_mmseqs_cluster
from thermo_mining.steps.prefilter import run_prefilter
from thermo_mining.steps.protrek_bridge import run_protrek_stage
from thermo_mining.steps.rerank import combine_stage_scores
from thermo_mining.steps.temstapro_screen import run_temstapro_screen


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_plan(run_dir: Path) -> dict[str, object]:
    return json.loads((run_dir / "execution_plan.json").read_text(encoding="utf-8"))


def _write_stage_state(run_dir: Path, status: str, active_stage: str | None) -> None:
    existing = json.loads((run_dir / "runtime_state.json").read_text(encoding="utf-8"))
    existing["status"] = status
    existing["active_stage"] = active_stage
    existing["updated_at"] = _now_iso()
    write_runtime_state(run_dir, existing)


def run_job(run_dir: str | Path) -> None:
    run_dir = Path(run_dir)
    plan = _load_plan(run_dir)
    bundle = plan["input_items"][0]
    bundle_type = plan["bundle_type"]
    current_input = Path(bundle["input_paths"][0])

    _write_stage_state(run_dir, "running", None)

    if bundle_type == "paired_fastq":
        _write_stage_state(run_dir, "running", "fastp")
        fastp_result = run_fastp_stage(
            read1=bundle["input_paths"][0],
            read2=bundle["input_paths"][1],
            stage_dir=run_dir / "01_fastp",
            fastp_bin="fastp",
        )
        _write_stage_state(run_dir, "running", "spades")
        spades_result = run_spades_stage(
            read1=fastp_result["read1"],
            read2=fastp_result["read2"],
            stage_dir=run_dir / "02_spades",
            spades_bin="spades.py",
            threads=32,
        )
        _write_stage_state(run_dir, "running", "prodigal")
        prodigal_result = run_prodigal_stage(
            contigs_fa=spades_result["contigs_fa"],
            stage_dir=run_dir / "03_prodigal",
            prodigal_bin="prodigal",
            software_version=__version__,
        )
        current_input = Path(prodigal_result["proteins_faa"])

    if bundle_type == "contigs":
        _write_stage_state(run_dir, "running", "prodigal")
        prodigal_result = run_prodigal_stage(
            contigs_fa=current_input,
            stage_dir=run_dir / "01_prodigal",
            prodigal_bin="prodigal",
            software_version=__version__,
        )
        current_input = Path(prodigal_result["proteins_faa"])

    _write_stage_state(run_dir, "running", "prefilter")
    prefilter_result = run_prefilter(
        input_faa=current_input,
        stage_dir=run_dir / "02_prefilter",
        min_length=80,
        max_length=1200,
        max_single_residue_fraction=0.7,
        software_version=__version__,
    )
    _write_stage_state(run_dir, "running", "mmseqs_cluster")
    cluster_result = run_mmseqs_cluster(
        input_faa=prefilter_result["filtered_faa"],
        stage_dir=run_dir / "03_cluster",
        mmseqs_bin="mmseqs",
        min_seq_id=0.9,
        coverage=0.8,
        threads=64,
        software_version=__version__,
    )
    _write_stage_state(run_dir, "running", "temstapro_screen")
    thermo_result = run_temstapro_screen(
        input_faa=cluster_result["cluster_rep_faa"],
        stage_dir=run_dir / "04_temstapro",
        temstapro_bin="temstapro",
        model_dir="/models/temstapro/ProtTrans",
        cache_dir="/tmp/temstapro_cache",
        top_fraction=0.1,
        min_score=0.5,
        software_version=__version__,
    )
    _write_stage_state(run_dir, "running", "protrek_recall")
    protrek_result = run_protrek_stage(
        input_faa=thermo_result["thermo_hits_faa"],
        stage_dir=run_dir / "05_protrek",
        python_bin="python",
        index_script="scripts/protrek_build_index.py",
        query_script="scripts/protrek_query.py",
        repo_root="/srv/ProTrek",
        weights_dir="/srv/ProTrek/weights/ProTrek_650M",
        query_texts=["thermostable enzyme"],
        batch_size=8,
        top_k=50,
        software_version=__version__,
    )
    _write_stage_state(run_dir, "running", "foldseek_confirm")
    foldseek_result = run_foldseek_stage(
        structure_manifest=[],
        stage_dir=run_dir / "06_foldseek",
        base_url="http://127.0.0.1:8100",
        database="afdb50",
        topk=5,
        min_tmscore=0.6,
        software_version=__version__,
    )

    combined_rows = combine_stage_scores(
        thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
        protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
        foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
        hot_spring_ids=set(),
    )
    write_report_outputs(run_dir / "07_report", Path(run_dir).name, combined_rows)
    _write_stage_state(run_dir, "succeeded", None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/runner.py tests/control_plane/test_runner.py
git commit -m "feat(control-plane): add bundle-aware runner"
```

### Task 8: Add A Tmux-Backed Job Manager With Single-Run Enforcement

**Files:**
- Create: `src/thermo_mining/control_plane/job_manager.py`
- Create: `tests/control_plane/test_job_manager.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from thermo_mining.control_plane.job_manager import ActiveRunConflict, JobManager
from thermo_mining.control_plane.run_store import create_pending_run
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _build_plan() -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    return ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="test plan",
    )


def test_confirm_run_builds_tmux_new_session_command(tmp_path, monkeypatch):
    commands: list[list[str]] = []
    monkeypatch.setattr("subprocess.run", lambda cmd, check: commands.append(cmd))
    record = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(record.run_id)

    assert commands[0][:3] == ["tmux", "new-session", "-d"]
    assert record.run_id in " ".join(commands[0])


def test_confirm_run_rejects_second_active_run(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda cmd, check: None)
    first = create_pending_run(tmp_path, _build_plan())
    second = create_pending_run(tmp_path, _build_plan())
    manager = JobManager(runs_root=tmp_path, tmux_bin="tmux")

    manager.confirm_run(first.run_id)
    with pytest.raises(ActiveRunConflict):
        manager.confirm_run(second.run_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_job_manager.py -v`
Expected: FAIL with `ModuleNotFoundError` for `job_manager`

- [ ] **Step 3: Write minimal implementation**

```python
import subprocess
from pathlib import Path

from .run_store import clear_active_run, read_active_run, set_active_run


class ActiveRunConflict(RuntimeError):
    pass


class JobManager:
    def __init__(self, runs_root: str | Path, tmux_bin: str) -> None:
        self.runs_root = Path(runs_root)
        self.tmux_bin = tmux_bin

    def _session_name(self, run_id: str) -> str:
        return f"thermo_{run_id}"

    def confirm_run(self, run_id: str) -> str:
        active = read_active_run(self.runs_root)
        if active and active != run_id:
            raise ActiveRunConflict(f"active run already exists: {active}")
        run_dir = self.runs_root / run_id
        session_name = self._session_name(run_id)
        command = [
            self.tmux_bin,
            "new-session",
            "-d",
            "-s",
            session_name,
            f"thermo-mining run-job --run-dir {run_dir}",
        ]
        subprocess.run(command, check=True)
        set_active_run(self.runs_root, run_id)
        return session_name

    def stop_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "send-keys", "-t", self._session_name(run_id), "C-c"], check=True)
        clear_active_run(self.runs_root)

    def terminate_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "kill-session", "-t", self._session_name(run_id)], check=True)
        clear_active_run(self.runs_root)

    def resume_run(self, run_id: str) -> str:
        return self.confirm_run(run_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_job_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/job_manager.py tests/control_plane/test_job_manager.py
git commit -m "feat(control-plane): add tmux-backed job manager"
```

### Task 9: Implement Planning, Fallback Parsing, And Failure Explanation

**Files:**
- Create: `src/thermo_mining/control_plane/llm_client.py`
- Create: `src/thermo_mining/control_plane/planner.py`
- Create: `src/thermo_mining/control_plane/status_explainer.py`
- Create: `tests/control_plane/test_planner.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.status_explainer import explain_failure
from thermo_mining.control_plane.stage_graph import build_stage_order


class FakeLLMClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def plan(self, **_: object) -> dict[str, object]:
        return self.payload


def test_plan_from_message_uses_valid_llm_payload():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    payload = {
        "assistant_message": "Planned the proteins flow",
        "execution_plan": {
            "bundle_type": "proteins",
            "input_items": [bundle.model_dump()],
            "stage_order": ["prefilter", "mmseqs_cluster"],
            "parameter_overrides": {},
            "output_root": "/runs/S01",
            "resume_policy": "if_possible",
            "requires_confirmation": True,
            "explanation": "Use the proteins-only path",
        },
        "plan_warnings": [],
    }

    result = plan_from_message("run the proteins file", [bundle], client=FakeLLMClient(payload))

    assert result["assistant_message"] == "Planned the proteins flow"
    assert result["execution_plan"].bundle_type == "proteins"


def test_plan_from_message_falls_back_when_llm_payload_is_invalid():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    result = plan_from_message("run default proteins pipeline", [bundle], client=FakeLLMClient({"oops": "bad"}))

    assert result["execution_plan"].bundle_type == "proteins"
    assert result["plan_warnings"]


def test_explain_failure_mentions_stage_and_error_summary():
    text = explain_failure({"active_stage": "mmseqs_cluster", "error_summary": "mmseqs exited with code 1"})

    assert "mmseqs_cluster" in text
    assert "code 1" in text


def test_apply_review_edits_rejects_non_editable_fields():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    plan = ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="planned",
    )

    from thermo_mining.control_plane.planner import apply_review_edits

    with pytest.raises(ValueError):
        apply_review_edits(plan, {"stage_order": ["bad"]})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/control_plane/test_planner.py -v`
Expected: FAIL with `ModuleNotFoundError` for `planner`

- [ ] **Step 3: Write minimal implementation**

```python
from openai import OpenAI


class OpenAIPlannerClient:
    def __init__(self, model: str, api_key: str | None, base_url: str | None) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def plan(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.output[0].content[0].json
```

```python
from .schemas import ExecutionPlan, InputBundle, REVIEW_EDITABLE_FIELDS
from .stage_graph import build_stage_order


def _fallback_plan(message: str, bundles: list[InputBundle]) -> dict[str, object]:
    bundle = bundles[0]
    return {
        "assistant_message": f"Using the fallback planner for {bundle.bundle_type}",
        "execution_plan": ExecutionPlan(
            bundle_type=bundle.bundle_type,
            input_items=[bundle],
            stage_order=build_stage_order(bundle.bundle_type),
            parameter_overrides={},
            output_root=bundle.output_root,
            resume_policy="if_possible",
            explanation=message,
        ),
        "plan_warnings": ["LLM output was invalid; fallback planning was used."],
    }


def plan_from_message(message: str, bundles: list[InputBundle], client: object) -> dict[str, object]:
    try:
        payload = client.plan(system_prompt="Return valid planning JSON", user_prompt=message)
        return {
            "assistant_message": payload["assistant_message"],
            "execution_plan": ExecutionPlan.model_validate(payload["execution_plan"]),
            "plan_warnings": payload.get("plan_warnings", []),
        }
    except Exception:
        return _fallback_plan(message, bundles)


def apply_review_edits(plan: ExecutionPlan, edits: dict[str, object]) -> ExecutionPlan:
    disallowed = set(edits) - REVIEW_EDITABLE_FIELDS
    if disallowed:
        raise ValueError(f"review edits contain non-editable fields: {sorted(disallowed)}")

    updated_payload = plan.model_dump()
    if "output_root" in edits:
        updated_payload["output_root"] = edits["output_root"]
    if "resume_policy" in edits:
        updated_payload["resume_policy"] = edits["resume_policy"]

    merged_overrides = dict(updated_payload["parameter_overrides"])
    for key, value in edits.items():
        if key not in {"output_root", "resume_policy"}:
            merged_overrides[key] = value
    updated_payload["parameter_overrides"] = merged_overrides
    return ExecutionPlan.model_validate(updated_payload)
```

```python
def explain_failure(runtime_state: dict[str, object]) -> str:
    stage = runtime_state.get("active_stage") or "unknown stage"
    summary = runtime_state.get("error_summary") or "no error summary was recorded"
    return f"The run failed during {stage}. Latest summary: {summary}."


def explain_run_status(runtime_state: dict[str, object]) -> str:
    status = runtime_state.get("status", "unknown")
    stage = runtime_state.get("active_stage") or "idle"
    return f"The run is currently {status}. Active stage: {stage}."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/control_plane/test_planner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/control_plane/llm_client.py src/thermo_mining/control_plane/planner.py src/thermo_mining/control_plane/status_explainer.py tests/control_plane/test_planner.py
git commit -m "feat(control-plane): add planner and failure explainer"
```

### Task 10: Expose Filesystem And Plan JSON APIs

**Files:**
- Create: `src/thermo_mining/web/__init__.py`
- Create: `src/thermo_mining/web/dependencies.py`
- Create: `src/thermo_mining/web/routes_api_fs.py`
- Create: `src/thermo_mining/web/routes_api_plan.py`
- Create: `src/thermo_mining/web/app.py`
- Create: `tests/web/test_fs_and_plan_api.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app


def test_fs_list_endpoint_returns_directory_rows(tmp_path):
    (tmp_path / "sample.faa").write_text(">p1\nAAAA\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/api/fs/list", params={"path": str(tmp_path.resolve())})

    assert response.status_code == 200
    assert response.json()[0]["name"] == "sample.faa"


def test_plan_endpoint_returns_structured_plan(monkeypatch):
    client = TestClient(create_app())

    def fake_plan_from_message(message, bundles, client):
        bundle = bundles[0]
        return {
            "assistant_message": "planned",
            "execution_plan": {
                "bundle_type": bundle.bundle_type,
                "input_items": [bundle.model_dump()],
                "stage_order": ["prefilter"],
                "parameter_overrides": {},
                "output_root": bundle.output_root,
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "planned",
            },
            "plan_warnings": [],
        }

    monkeypatch.setattr("thermo_mining.web.routes_api_plan.plan_from_message", fake_plan_from_message)

    response = client.post(
        "/api/plan",
        json={
            "message": "plan this",
            "selected_bundles": [
                {
                    "bundle_type": "proteins",
                    "sample_id": "S01",
                    "input_paths": ["/mnt/disk2/S01.faa"],
                    "metadata": {},
                    "output_root": "/runs/S01",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["assistant_message"] == "planned"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_fs_and_plan_api.py -v`
Expected: FAIL with `ModuleNotFoundError` for `thermo_mining.web`

- [ ] **Step 3: Write minimal implementation**

```python
"""FastAPI web layer for the thermo mining control plane."""
```

```python
from pathlib import Path

from thermo_mining.control_plane.job_manager import JobManager
from thermo_mining.control_plane.llm_client import OpenAIPlannerClient
from thermo_mining.settings import PlatformSettings, load_settings


def get_settings() -> PlatformSettings:
    return load_settings("config/platform.example.yaml")


def get_llm_client() -> OpenAIPlannerClient:
    settings = get_settings()
    return OpenAIPlannerClient(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
    )


def get_job_manager() -> JobManager:
    settings = get_settings()
    return JobManager(runs_root=settings.runtime.runs_root, tmux_bin=settings.tools.tmux_bin)
```

```python
from pathlib import Path

from fastapi import APIRouter, Query

from thermo_mining.control_plane.fastq_pairing import detect_fastq_pairs, scan_input_bundles
from thermo_mining.control_plane.fs_service import list_path_entries, search_path_entries

router = APIRouter(prefix="/api/fs", tags=["fs"])


@router.get("/list")
def fs_list(path: str = Query(...)) -> list[dict[str, object]]:
    return [row.model_dump() for row in list_path_entries(path)]


@router.get("/search")
def fs_search(root: str, q: str) -> list[dict[str, object]]:
    return [row.model_dump() for row in search_path_entries(root, q)]


@router.post("/pair-fastq")
def pair_fastq(payload: dict[str, list[str]]) -> list[dict[str, object]]:
    return [row.model_dump() for row in detect_fastq_pairs([Path(item) for item in payload["paths"]])]


@router.post("/scan-bundles")
def scan_bundles(payload: dict[str, str]) -> list[dict[str, object]]:
    return [row.model_dump() for row in scan_input_bundles(payload["root"], payload["output_root"])]
```

```python
from fastapi import APIRouter

from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.web.dependencies import get_llm_client

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan")
def create_plan(payload: dict[str, object]) -> dict[str, object]:
    bundles = [InputBundle.model_validate(row) for row in payload["selected_bundles"]]
    planned = plan_from_message(str(payload["message"]), bundles, client=get_llm_client())
    execution_plan = planned["execution_plan"]
    if isinstance(execution_plan, dict):
        execution_plan = ExecutionPlan.model_validate(execution_plan)
    return {
        "assistant_message": planned["assistant_message"],
        "execution_plan": execution_plan.model_dump(),
        "plan_warnings": planned["plan_warnings"],
    }
```

```python
from fastapi import FastAPI

from .routes_api_fs import router as fs_router
from .routes_api_plan import router as plan_router


def create_app() -> FastAPI:
    app = FastAPI(title="Thermo Mining Control Plane")
    app.include_router(fs_router)
    app.include_router(plan_router)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_fs_and_plan_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/web/__init__.py src/thermo_mining/web/dependencies.py src/thermo_mining/web/routes_api_fs.py src/thermo_mining/web/routes_api_plan.py src/thermo_mining/web/app.py tests/web/test_fs_and_plan_api.py
git commit -m "feat(control-plane): add filesystem and plan apis"
```

### Task 11: Expose Run Lifecycle And Restricted Chat APIs

**Files:**
- Create: `src/thermo_mining/web/routes_api_runs.py`
- Create: `src/thermo_mining/web/routes_api_chat.py`
- Modify: `src/thermo_mining/web/app.py`
- Create: `tests/web/test_runs_and_chat_api.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app


def test_confirm_run_endpoint_delegates_to_job_manager(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr("thermo_mining.web.routes_api_runs.create_pending_run", lambda runs_root, plan: type("Record", (), {"run_id": "run_001"})())
    monkeypatch.setattr("thermo_mining.web.routes_api_runs.ExecutionPlan.model_validate", lambda payload: payload)
    monkeypatch.setattr("thermo_mining.web.routes_api_runs.get_settings", lambda: type("Settings", (), {"runtime": type("Runtime", (), {"runs_root": "/runs"})()})())
    monkeypatch.setattr("thermo_mining.web.routes_api_runs.get_job_manager", lambda: type("Manager", (), {"confirm_run": lambda self, run_id: "thermo_run_001"})())

    create_response = client.post(
        "/api/runs",
        json={
            "bundle_type": "proteins",
            "input_items": [],
            "stage_order": ["prefilter"],
            "parameter_overrides": {},
            "output_root": "/runs/S01",
            "resume_policy": "if_possible",
            "requires_confirmation": True,
            "explanation": "planned",
        },
    )
    confirm_response = client.post("/api/runs/run_001/confirm")

    assert create_response.status_code == 200
    assert confirm_response.status_code == 200
    assert confirm_response.json()["tmux_session"] == "thermo_run_001"


def test_openai_compatible_chat_returns_message_content(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.explain_run_status",
        lambda runtime_state: "The run is currently idle.",
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.read_active_run",
        lambda runs_root: None,
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.get_settings",
        lambda: type("Settings", (), {"runtime": type("Runtime", (), {"runs_root": "/runs"})()})(),
    )

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "what is the current run status"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "The run is currently idle."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_runs_and_chat_api.py -v`
Expected: FAIL with missing run/chat routes

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import APIRouter, HTTPException

from thermo_mining.control_plane.planner import apply_review_edits, plan_from_message
from thermo_mining.control_plane.run_store import create_pending_run, list_artifacts, read_active_run
from thermo_mining.control_plane.schemas import ExecutionPlan
from thermo_mining.control_plane.schemas import InputBundle
from thermo_mining.web.dependencies import get_job_manager, get_llm_client, get_settings

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
def create_run(payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    if read_active_run(settings.runtime.runs_root):
        raise HTTPException(status_code=409, detail="an active run already exists")
    base_plan = ExecutionPlan.model_validate(payload["execution_plan"] if "execution_plan" in payload else payload)
    plan = apply_review_edits(base_plan, payload.get("review_edits", {}))
    record = create_pending_run(settings.runtime.runs_root, plan)
    return {"run_id": record.run_id}


@router.post("/{run_id}/confirm")
def confirm_run(run_id: str) -> dict[str, object]:
    session_name = get_job_manager().confirm_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.post("/{run_id}/stop")
def stop_run(run_id: str) -> dict[str, object]:
    get_job_manager().stop_run(run_id)
    return {"run_id": run_id, "status": "stopped"}


@router.post("/{run_id}/terminate")
def terminate_run(run_id: str) -> dict[str, object]:
    get_job_manager().terminate_run(run_id)
    return {"run_id": run_id, "status": "failed"}


@router.post("/{run_id}/resume")
def resume_run(run_id: str) -> dict[str, object]:
    session_name = get_job_manager().resume_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.get("/active")
def get_active_run() -> dict[str, object]:
    from thermo_mining.control_plane.run_store import read_active_run

    run_id = read_active_run(get_settings().runtime.runs_root)
    return {"run_id": run_id}


@router.get("/{run_id}")
def get_run_detail(run_id: str) -> dict[str, object]:
    return {"run_id": run_id}


@router.get("/{run_id}/logs")
def get_run_logs(run_id: str) -> dict[str, object]:
    return {"run_id": run_id, "lines": []}


@router.get("/{run_id}/artifacts")
def get_run_artifacts(run_id: str) -> list[dict[str, object]]:
    run_dir = get_settings().runtime.runs_root / run_id
    return [row.model_dump() for row in list_artifacts(run_dir)]
```

```python
from fastapi import APIRouter

from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.run_store import read_active_run
from thermo_mining.control_plane.schemas import InputBundle
from thermo_mining.control_plane.status_explainer import explain_failure, explain_run_status
from thermo_mining.web.dependencies import get_llm_client, get_settings

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
def chat_completions(payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    runs_root = settings.runtime.runs_root
    active_run = read_active_run(runs_root)
    if payload.get("selected_bundles"):
        bundles = [InputBundle.model_validate(row) for row in payload["selected_bundles"]]
        planned = plan_from_message(
            str(payload["messages"][-1]["content"]),
            bundles,
            client=get_llm_client(),
        )
        content = planned["assistant_message"]
    elif payload.get("runtime_state", {}).get("status") == "failed":
        content = explain_failure(payload["runtime_state"])
    elif active_run is None:
        content = explain_run_status({"status": "idle", "active_stage": None})
    else:
        content = explain_run_status({"status": "running", "active_stage": "unknown"})
    return {
        "id": "chatcmpl-control-plane",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }
```

```python
from fastapi import FastAPI

from .routes_api_chat import router as chat_router
from .routes_api_fs import router as fs_router
from .routes_api_plan import router as plan_router
from .routes_api_runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Thermo Mining Control Plane")
    app.include_router(fs_router)
    app.include_router(plan_router)
    app.include_router(runs_router)
    app.include_router(chat_router)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_runs_and_chat_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/web/routes_api_runs.py src/thermo_mining/web/routes_api_chat.py src/thermo_mining/web/app.py tests/web/test_runs_and_chat_api.py
git commit -m "feat(control-plane): add run and chat apis"
```

### Task 12: Build The Web Console, Final CLI Wiring, And Deployment Scripts

**Files:**
- Create: `src/thermo_mining/web/routes_pages.py`
- Create: `src/thermo_mining/web/templates/index.html`
- Create: `src/thermo_mining/web/static/console.js`
- Create: `src/thermo_mining/web/static/console.css`
- Modify: `src/thermo_mining/web/app.py`
- Modify: `src/thermo_mining/cli.py`
- Modify: `README.md`
- Create: `scripts/start_web.sh`
- Create: `scripts/start_all.sh`
- Create: `scripts/status.sh`
- Create: `scripts/stop.sh`
- Create: `tests/web/test_pages.py`
- Modify: `tests/test_control_plane_bootstrap.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from thermo_mining.cli import main
from thermo_mining.web.app import create_app


def test_index_page_contains_expected_console_sections():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Chat" in response.text
    assert "Plan Review" in response.text
    assert "Run Monitor" in response.text
    assert "Artifacts" in response.text


def test_cli_main_dispatches_serve_and_run_job(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr("thermo_mining.cli.serve_app", lambda config_path, host, port: captured.update({"serve": (config_path, host, port)}))
    monkeypatch.setattr("thermo_mining.cli.run_job", lambda run_dir, config_path=None: captured.update({"run_job": (run_dir, config_path)}))

    main(["serve", "--config", "config/platform.example.yaml", "--host", "0.0.0.0", "--port", "9000"])
    main(["run-job", "--config", "config/platform.example.yaml", "--run-dir", str(tmp_path / "run_001")])

    assert captured["serve"][1:] == ("0.0.0.0", 9000)
    assert str(tmp_path / "run_001") in str(captured["run_job"][0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_pages.py tests/test_control_plane_bootstrap.py -v`
Expected: FAIL because the page route and CLI dispatch are not implemented

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from importlib.resources import files


templates = Jinja2Templates(directory=str(files("thermo_mining.web").joinpath("templates")))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})
```

```python
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Thermo Mining Control Plane</title>
    <link rel="stylesheet" href="/static/console.css" />
  </head>
  <body>
    <header><h1>Thermo Mining Control Plane</h1></header>
    <main class="layout">
      <section id="chat-panel"><h2>Chat</h2><div id="chat-thread"></div></section>
      <section id="plan-panel"><h2>Plan Review</h2><div id="plan-review"></div></section>
      <section id="run-panel"><h2>Run Monitor</h2><div id="run-monitor"></div></section>
      <section id="artifacts-panel"><h2>Artifacts</h2><div id="artifact-list"></div></section>
    </main>
    <dialog id="file-browser-modal">
      <h2>Server Path Browser</h2>
      <div id="file-browser-results"></div>
      <button id="close-browser" type="button">Close</button>
    </dialog>
    <script src="/static/console.js"></script>
  </body>
</html>
```

```javascript
const state = {
  chat: JSON.parse(window.localStorage.getItem("thermo-chat") || "[]"),
  latestPlan: null,
};

async function openFileBrowser(path) {
  const response = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
  const rows = await response.json();
  document.getElementById("file-browser-results").textContent = rows.map((row) => row.path).join("\n");
  document.getElementById("file-browser-modal").showModal();
}

async function refreshActiveRun() {
  const response = await fetch("/api/runs/active");
  const payload = await response.json();
  document.getElementById("run-monitor").textContent = payload.run_id ? `Active run: ${payload.run_id}` : "No active run";
}

window.addEventListener("load", () => {
  document.getElementById("close-browser").addEventListener("click", () => {
    document.getElementById("file-browser-modal").close();
  });
  refreshActiveRun();
  window.setInterval(refreshActiveRun, 2000);
});
```

```css
body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background: linear-gradient(180deg, #f7f3eb 0%, #efe8d8 100%);
  color: #1e241d;
}

.layout {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  grid-template-areas:
    "chat plan"
    "chat run"
    "artifacts artifacts";
  gap: 16px;
  padding: 16px;
}

#chat-panel { grid-area: chat; }
#plan-panel { grid-area: plan; }
#run-panel { grid-area: run; }
#artifacts-panel { grid-area: artifacts; }
section {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(30, 36, 29, 0.12);
  border-radius: 14px;
  padding: 16px;
}
```

```python
from pathlib import Path

import uvicorn

from .pipeline import run_pipeline


def serve_app(config_path: str | Path, host: str | None, port: int | None) -> None:
    app_host = host or "127.0.0.1"
    app_port = port or 8000
    uvicorn.run("thermo_mining.web.app:create_app", factory=True, host=app_host, port=app_port)


def run_job(run_dir: str | Path, config_path: str | Path | None = None) -> None:
    from thermo_mining.control_plane.runner import run_job as runner_run_job

    runner_run_job(Path(run_dir))


def main(argv: list[str] | None = None) -> dict[str, object] | None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_pipeline(
            config_path=Path(args.config),
            run_name=args.run_name,
            input_faa=Path(args.input_faa),
            resume=args.resume,
        )
    if args.command == "serve":
        serve_app(args.config, args.host, args.port)
        return None
    if args.command == "run-job":
        run_job(args.run_dir, args.config)
        return None
    return None
```

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from importlib.resources import files

from .routes_api_chat import router as chat_router
from .routes_api_fs import router as fs_router
from .routes_api_plan import router as plan_router
from .routes_api_runs import router as runs_router
from .routes_pages import router as page_router


def create_app() -> FastAPI:
    app = FastAPI(title="Thermo Mining Control Plane")
    app.include_router(page_router)
    app.include_router(fs_router)
    app.include_router(plan_router)
    app.include_router(runs_router)
    app.include_router(chat_router)
    app.mount("/static", StaticFiles(directory=str(files("thermo_mining.web").joinpath("static"))), name="static")
    return app
```

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
nohup thermo-mining serve --config config/platform.example.yaml > logs/web.log 2>&1 &
echo $! > logs/web.pid
echo "web started"
```

```bash
#!/usr/bin/env bash
set -euo pipefail
./scripts/start_web.sh
echo "worker model is on-demand via tmux sessions created at confirm time"
```

```bash
#!/usr/bin/env bash
set -euo pipefail
if [[ -f logs/web.pid ]]; then
  echo "web pid: $(cat logs/web.pid)"
else
  echo "web not running"
fi
thermo-mining serve --help >/dev/null
```

```bash
#!/usr/bin/env bash
set -euo pipefail
if [[ -f logs/web.pid ]]; then
  kill "$(cat logs/web.pid)"
  rm -f logs/web.pid
fi
echo "web stopped"
```

```markdown
# Thermo Mining

## CLI

- `thermo-mining run ...`
- `thermo-mining serve --config config/platform.example.yaml`
- `thermo-mining run-job --run-dir runs/<run_id>`

## Control Plane MVP

- Single-user FastAPI console
- Server-side path browsing
- Plan review and confirm flow
- One active tmux-backed run at a time
- Artifacts and runtime status from `runtime_state.json`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_pages.py tests/test_control_plane_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/web/routes_pages.py src/thermo_mining/web/templates/index.html src/thermo_mining/web/static/console.js src/thermo_mining/web/static/console.css src/thermo_mining/web/app.py src/thermo_mining/cli.py README.md scripts/start_web.sh scripts/start_all.sh scripts/status.sh scripts/stop.sh tests/web/test_pages.py tests/test_control_plane_bootstrap.py
git commit -m "feat(control-plane): add web console and deployment scripts"
```

## Self-Review

### Spec coverage

- Product boundary and locked decisions: Task 1, Task 2, Task 9, Task 10, Task 11, Task 12
- Web/API layer: Task 10, Task 11, Task 12
- Planner layer and restricted chat behavior: Task 9, Task 11
- Filesystem layer and arbitrary absolute-path browsing: Task 3, Task 4, Task 10
- Job manager and single active run: Task 5, Task 8, Task 11
- Runner and bundle-specific execution graph: Task 2, Task 6, Task 7
- Runtime layout and `runtime_state.json`: Task 5, Task 7
- `tmux` lifecycle and resume semantics: Task 8, Task 11
- UI surface (`Chat`, `Plan Review`, `Run Monitor`, `Artifacts`): Task 12
- Deployment assumptions: Task 1, Task 12

No spec section is left without at least one implementation task.

### Placeholder scan

There are no `TBD`, `TODO`, “implement later”, or cross-task “same as above” placeholders in the plan. Every task lists exact files, concrete tests, explicit commands, and minimal code to write.

### Type consistency

- Bundle type names are consistently `paired_fastq`, `contigs`, and `proteins`
- Runtime status values are consistently `pending`, `running`, `succeeded`, `failed`, and `stopped`
- The shared core models are introduced in Task 2 and reused consistently later
- Route names and file names align with the file map and the spec
- CLI commands remain `run`, `serve`, and `run-job` throughout the plan
