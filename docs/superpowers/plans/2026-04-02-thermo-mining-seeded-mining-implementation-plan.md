# Thermo Mining Seeded Mining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `seeded_proteins` runtime that accepts one seed FASTA plus one target FASTA, performs dual recall on compressed target proteins, and feeds recalled targets into the existing thermo-mining cascade.

**Architecture:** Keep the current `proteins` flow unchanged and add a parallel seeded contract instead of overloading single-input behavior. Implement the feature through three new seed-specific step modules, shared report/schema/default extensions, a new CLI entry point, and control-plane runner support that short-circuits cleanly when no seed-guided hits survive.

**Tech Stack:** Python 3.11, Pydantic v2, PyYAML, pytest, MMseqs2, LocalColabFold, Foldseek, existing `thermo_mining` pipeline helpers

---

## File Structure

### Core runtime and contracts

- Modify `src/thermo_mining/settings.py`
  - Add seeded recall defaults and environment variable loading.
- Modify `src/thermo_mining/control_plane/schemas.py`
  - Add `seeded_proteins` bundle type and explicit `seed_paths`.
- Modify `src/thermo_mining/control_plane/stage_graph.py`
  - Register the seeded stage order.
- Modify `src/thermo_mining/stage_layout.py`
  - Add stage suffixes for the three seed-specific stages.
- Modify `src/thermo_mining/cli.py`
  - Add `run-seeded` and dispatch into the seeded pipeline entry point.
- Modify `config/platform.example.yaml`
  - Document seeded defaults.
- Modify `config/platform.server.ubuntu.yaml`
  - Carry the same seeded defaults in the server draft.

### Seed-specific steps

- Create `src/thermo_mining/steps/seed_sequence_recall.py`
  - Sequence recall against clustered representative targets via `mmseqs easy-search`.
- Create `src/thermo_mining/steps/seed_structure_recall.py`
  - Structure prediction for seeds and clustered target representatives, local Foldseek DB creation, and per-seed structural recall.
- Create `src/thermo_mining/steps/seed_recall_merge.py`
  - Union merge for sequence and structure recall hits plus `seeded_targets.faa` generation.

### Shared scoring and reporting

- Modify `src/thermo_mining/steps/rerank.py`
  - Merge optional seed provenance into final rows without changing the final-score formula.
- Modify `src/thermo_mining/reporting.py`
  - Extend report fieldnames and preserve empty-report output behavior.

### Pipeline and control plane orchestration

- Modify `src/thermo_mining/pipeline.py`
  - Add `run_seeded_pipeline()` and empty-recall short-circuit.
- Modify `src/thermo_mining/control_plane/planner.py`
  - Include `seed_paths` in prompt generation and bundle validation.
- Modify `src/thermo_mining/control_plane/runner.py`
  - Execute the seeded stage graph and skip downstream thermo stages on empty merged recall.

### Tests

- Modify `tests/test_settings.py`
- Modify `tests/control_plane/test_schemas.py`
- Modify `tests/control_plane/test_planner.py`
- Modify `tests/control_plane/test_runner.py`
- Modify `tests/test_pipeline_cli.py`
- Modify `tests/steps/test_rerank.py`
- Create `tests/steps/test_seed_sequence_recall.py`
- Create `tests/steps/test_seed_structure_recall.py`
- Create `tests/steps/test_seed_recall_merge.py`

### Naming contract to keep consistent across tasks

- `run_seed_sequence_recall_stage(...)`
- `run_seed_structure_recall_stage(...)`
- `run_seed_recall_merge_stage(...)`
- `run_seeded_pipeline(...)`
- `seed_rows` as the optional provenance parameter for `combine_stage_scores(...)`

### Delivery order

1. Shared contracts and defaults
2. Planner awareness
3. Seed sequence recall
4. Seed structure recall
5. Seed merge plus reporting
6. Seeded CLI pipeline
7. Seeded control-plane runner

## Task 1: Add Seeded Contracts And Defaults

**Files:**
- Modify: `src/thermo_mining/settings.py`
- Modify: `src/thermo_mining/control_plane/schemas.py`
- Modify: `src/thermo_mining/control_plane/stage_graph.py`
- Modify: `src/thermo_mining/stage_layout.py`
- Modify: `config/platform.example.yaml`
- Modify: `config/platform.server.ubuntu.yaml`
- Test: `tests/test_settings.py`
- Test: `tests/control_plane/test_schemas.py`

- [ ] **Step 1: Write the failing schema and settings tests**

Add these tests to `tests/control_plane/test_schemas.py`:

```python
def test_seeded_input_bundle_requires_one_seed_and_one_target():
    bundle = InputBundle(
        bundle_type="seeded_proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/targets.faa"],
        seed_paths=["/mnt/disk2/cas_seed_queries.faa"],
        metadata={},
        output_root="/runs/S01",
    )

    assert bundle.seed_paths == ["/mnt/disk2/cas_seed_queries.faa"]
    assert bundle.input_paths == ["/mnt/disk2/targets.faa"]

    with pytest.raises(ValidationError):
        InputBundle(
            bundle_type="seeded_proteins",
            sample_id="S01",
            input_paths=["/mnt/disk2/targets.faa"],
            seed_paths=[],
            metadata={},
            output_root="/runs/S01",
        )

    with pytest.raises(ValidationError):
        InputBundle(
            bundle_type="seeded_proteins",
            sample_id="S01",
            input_paths=["/mnt/disk2/targets_a.faa", "/mnt/disk2/targets_b.faa"],
            seed_paths=["/mnt/disk2/cas_seed_queries.faa"],
            metadata={},
            output_root="/runs/S01",
        )


def test_non_seeded_input_bundle_rejects_seed_paths():
    with pytest.raises(ValidationError):
        InputBundle(
            bundle_type="proteins",
            sample_id="S01",
            input_paths=["/mnt/disk2/S01.faa"],
            seed_paths=["/mnt/disk2/cas_seed_queries.faa"],
            metadata={},
            output_root="/runs/S01",
        )


def test_build_stage_order_includes_seeded_proteins():
    assert build_stage_order("seeded_proteins") == [
        "prefilter",
        "mmseqs_cluster",
        "seed_sequence_recall",
        "seed_structure_recall",
        "seed_recall_merge",
        "temstapro_screen",
        "protrek_recall",
        "structure_predict",
        "foldseek_confirm",
        "rerank_report",
    ]
```

Append this test to `tests/test_settings.py`:

```python
def test_load_settings_reads_seeded_defaults_from_yaml_and_env(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
defaults:
  seed_sequence_min_seq_id: 0.33
  seed_sequence_coverage: 0.81
  seed_sequence_topk_per_seed: 123
  seed_structure_min_tmscore: 0.58
  seed_structure_topk_per_seed: 222
  seed_structure_max_targets: 444
""".strip(),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
THERMO_DEFAULT_SEED_SEQUENCE_TOPK_PER_SEED=321
THERMO_DEFAULT_SEED_STRUCTURE_MAX_TARGETS=555
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=env_path)

    assert settings.defaults.seed_sequence_min_seq_id == 0.33
    assert settings.defaults.seed_sequence_coverage == 0.81
    assert settings.defaults.seed_sequence_topk_per_seed == 321
    assert settings.defaults.seed_structure_min_tmscore == 0.58
    assert settings.defaults.seed_structure_topk_per_seed == 222
    assert settings.defaults.seed_structure_max_targets == 555
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/control_plane/test_schemas.py tests/test_settings.py -v
```

Expected:

- FAIL because `seeded_proteins` is not a valid `BundleType`
- FAIL because `InputBundle` has no `seed_paths`
- FAIL because `DefaultSettings` and `load_settings()` do not expose seeded defaults yet

- [ ] **Step 3: Implement seeded bundle contracts, defaults, and config docs**

Update `src/thermo_mining/control_plane/schemas.py`:

```python
import ntpath
import posixpath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

BundleType = Literal["paired_fastq", "contigs", "proteins", "seeded_proteins"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "stopped"]


class InputBundle(BaseModel):
    bundle_type: BundleType
    sample_id: str
    input_paths: list[str]
    seed_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_root: str

    @field_validator("input_paths", "seed_paths")
    @classmethod
    def validate_absolute_paths(cls, value: list[str]) -> list[str]:
        for item in value:
            if not (posixpath.isabs(item) or ntpath.isabs(item)):
                raise ValueError("input paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_bundle_shape(self) -> "InputBundle":
        if self.bundle_type == "seeded_proteins":
            if len(self.input_paths) != 1:
                raise ValueError("seeded_proteins bundles require exactly one target input path")
            if len(self.seed_paths) != 1:
                raise ValueError("seeded_proteins bundles require exactly one seed path")
            return self

        if self.seed_paths:
            raise ValueError("seed paths are only supported for seeded_proteins bundles")
        return self
```

Update `src/thermo_mining/control_plane/stage_graph.py`:

```python
STAGE_ORDERS: dict[BundleType, list[str]] = {
    "paired_fastq": [
        "fastp",
        "spades",
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "structure_predict",
        "foldseek_confirm",
        "rerank_report",
    ],
    "contigs": [
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "structure_predict",
        "foldseek_confirm",
        "rerank_report",
    ],
    "proteins": [
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "structure_predict",
        "foldseek_confirm",
        "rerank_report",
    ],
    "seeded_proteins": [
        "prefilter",
        "mmseqs_cluster",
        "seed_sequence_recall",
        "seed_structure_recall",
        "seed_recall_merge",
        "temstapro_screen",
        "protrek_recall",
        "structure_predict",
        "foldseek_confirm",
        "rerank_report",
    ],
}
```

Update `src/thermo_mining/stage_layout.py`:

```python
STAGE_DIR_SUFFIXES: dict[str, str] = {
    "fastp": "fastp",
    "spades": "spades",
    "prodigal": "prodigal",
    "prefilter": "prefilter",
    "mmseqs_cluster": "cluster",
    "seed_sequence_recall": "seed_sequence",
    "seed_structure_recall": "seed_structure",
    "seed_recall_merge": "seed_merge",
    "temstapro_screen": "temstapro",
    "protrek_recall": "protrek",
    "structure_predict": "structure",
    "foldseek_confirm": "foldseek",
    "rerank_report": "report",
}
```

Update `src/thermo_mining/settings.py` by extending `DefaultSettings`:

```python
@dataclass(frozen=True)
class DefaultSettings:
    prefilter_min_length: int = 80
    prefilter_max_length: int = 1200
    prefilter_max_single_residue_fraction: float = 0.7
    cluster_min_seq_id: float = 0.9
    cluster_coverage: float = 0.8
    cluster_threads: int = 64
    thermo_top_fraction: float = 0.1
    thermo_min_score: float = 0.5
    protrek_query_texts: tuple[str, ...] = field(
        default_factory=lambda: ("thermostable enzyme", "heat-stable protein")
    )
    protrek_batch_size: int = 8
    protrek_top_k: int = 50
    seed_sequence_min_seq_id: float = 0.30
    seed_sequence_coverage: float = 0.80
    seed_sequence_topk_per_seed: int = 200
    seed_structure_min_tmscore: float = 0.55
    seed_structure_topk_per_seed: int = 200
    seed_structure_max_targets: int = 500
    colabfold_msa_mode: str = "single_sequence"
    colabfold_num_models: int = 1
    colabfold_num_recycle: int = 1
    foldseek_topk: int = 5
    foldseek_min_tmscore: float = 0.6
```

Add the matching environment-backed load logic inside `load_settings()`:

```python
        defaults=DefaultSettings(
            prefilter_min_length=_env_int(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MIN_LENGTH",
                int(defaults_raw.get("prefilter_min_length", 80)),
            ),
            prefilter_max_length=_env_int(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MAX_LENGTH",
                int(defaults_raw.get("prefilter_max_length", 1200)),
            ),
            prefilter_max_single_residue_fraction=_env_float(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MAX_SINGLE_RESIDUE_FRACTION",
                float(defaults_raw.get("prefilter_max_single_residue_fraction", 0.7)),
            ),
            cluster_min_seq_id=_env_float(
                env_data,
                "THERMO_DEFAULT_CLUSTER_MIN_SEQ_ID",
                float(defaults_raw.get("cluster_min_seq_id", 0.9)),
            ),
            cluster_coverage=_env_float(
                env_data,
                "THERMO_DEFAULT_CLUSTER_COVERAGE",
                float(defaults_raw.get("cluster_coverage", 0.8)),
            ),
            cluster_threads=_env_int(
                env_data,
                "THERMO_DEFAULT_CLUSTER_THREADS",
                int(defaults_raw.get("cluster_threads", 64)),
            ),
            thermo_top_fraction=_env_float(
                env_data,
                "THERMO_DEFAULT_THERMO_TOP_FRACTION",
                float(defaults_raw.get("thermo_top_fraction", 0.1)),
            ),
            thermo_min_score=_env_float(
                env_data,
                "THERMO_DEFAULT_THERMO_MIN_SCORE",
                float(defaults_raw.get("thermo_min_score", 0.5)),
            ),
            protrek_query_texts=_env_list(
                env_data,
                "THERMO_DEFAULT_PROTREK_QUERY_TEXTS",
                tuple(defaults_raw.get("protrek_query_texts", ("thermostable enzyme", "heat-stable protein"))),
            ),
            protrek_batch_size=_env_int(
                env_data,
                "THERMO_DEFAULT_PROTREK_BATCH_SIZE",
                int(defaults_raw.get("protrek_batch_size", 8)),
            ),
            protrek_top_k=_env_int(
                env_data,
                "THERMO_DEFAULT_PROTREK_TOP_K",
                int(defaults_raw.get("protrek_top_k", 50)),
            ),
            seed_sequence_min_seq_id=_env_float(
                env_data,
                "THERMO_DEFAULT_SEED_SEQUENCE_MIN_SEQ_ID",
                float(defaults_raw.get("seed_sequence_min_seq_id", 0.30)),
            ),
            seed_sequence_coverage=_env_float(
                env_data,
                "THERMO_DEFAULT_SEED_SEQUENCE_COVERAGE",
                float(defaults_raw.get("seed_sequence_coverage", 0.80)),
            ),
            seed_sequence_topk_per_seed=_env_int(
                env_data,
                "THERMO_DEFAULT_SEED_SEQUENCE_TOPK_PER_SEED",
                int(defaults_raw.get("seed_sequence_topk_per_seed", 200)),
            ),
            seed_structure_min_tmscore=_env_float(
                env_data,
                "THERMO_DEFAULT_SEED_STRUCTURE_MIN_TMSCORE",
                float(defaults_raw.get("seed_structure_min_tmscore", 0.55)),
            ),
            seed_structure_topk_per_seed=_env_int(
                env_data,
                "THERMO_DEFAULT_SEED_STRUCTURE_TOPK_PER_SEED",
                int(defaults_raw.get("seed_structure_topk_per_seed", 200)),
            ),
            seed_structure_max_targets=_env_int(
                env_data,
                "THERMO_DEFAULT_SEED_STRUCTURE_MAX_TARGETS",
                int(defaults_raw.get("seed_structure_max_targets", 500)),
            ),
            colabfold_msa_mode=_env_text(
                env_data,
                "THERMO_DEFAULT_COLABFOLD_MSA_MODE",
                str(defaults_raw.get("colabfold_msa_mode", "single_sequence")),
            )
            or "single_sequence",
            colabfold_num_models=_env_int(
                env_data,
                "THERMO_DEFAULT_COLABFOLD_NUM_MODELS",
                int(defaults_raw.get("colabfold_num_models", 1)),
            ),
            colabfold_num_recycle=_env_int(
                env_data,
                "THERMO_DEFAULT_COLABFOLD_NUM_RECYCLE",
                int(defaults_raw.get("colabfold_num_recycle", 1)),
            ),
            foldseek_topk=_env_int(
                env_data,
                "THERMO_DEFAULT_FOLDSEEK_TOPK",
                int(defaults_raw.get("foldseek_topk", 5)),
            ),
            foldseek_min_tmscore=_env_float(
                env_data,
                "THERMO_DEFAULT_FOLDSEEK_MIN_TMSCORE",
                float(defaults_raw.get("foldseek_min_tmscore", 0.6)),
            ),
        ),
```

Append the seeded defaults to both YAML files:

```yaml
  seed_sequence_min_seq_id: 0.30
  seed_sequence_coverage: 0.80
  seed_sequence_topk_per_seed: 200
  seed_structure_min_tmscore: 0.55
  seed_structure_topk_per_seed: 200
  seed_structure_max_targets: 500
```

- [ ] **Step 4: Run the targeted tests again**

Run:

```bash
pytest tests/control_plane/test_schemas.py tests/test_settings.py -v
```

Expected:

- PASS
- seeded bundle validation accepts exactly one seed and one target
- seeded defaults load from YAML and environment variables

- [ ] **Step 5: Commit the contract/default changes**

Run:

```bash
git add tests/control_plane/test_schemas.py tests/test_settings.py src/thermo_mining/control_plane/schemas.py src/thermo_mining/control_plane/stage_graph.py src/thermo_mining/stage_layout.py src/thermo_mining/settings.py config/platform.example.yaml config/platform.server.ubuntu.yaml
git commit -m "feat(seeded): add seeded runtime contract"
```

## Task 2: Make The Planner Seed-Aware

**Files:**
- Modify: `src/thermo_mining/control_plane/planner.py`
- Test: `tests/control_plane/test_planner.py`

- [ ] **Step 1: Write failing planner tests for `seed_paths`**

Append these tests to `tests/control_plane/test_planner.py`:

```python
def test_plan_from_message_includes_seed_paths_in_prompt():
    bundle = InputBundle(
        bundle_type="seeded_proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/targets.faa"],
        seed_paths=["/mnt/disk2/cas_seed_queries.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    client = FakeLLMClient(
        {
            "assistant_message": "Planned the seeded proteins flow",
            "execution_plan": {
                "bundle_type": "seeded_proteins",
                "input_items": [bundle.model_dump()],
                "stage_order": build_stage_order("seeded_proteins"),
                "parameter_overrides": {},
                "output_root": "/runs/S01",
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "Use the seeded proteins path",
            },
            "plan_warnings": [],
        }
    )

    plan_from_message("mine targets using the cas seeds", [bundle], client=client)

    assert "bundle_type: seeded_proteins" in client.calls[0]["user_prompt"]
    assert "seed_paths: /mnt/disk2/cas_seed_queries.faa" in client.calls[0]["user_prompt"]
    assert "input_paths: /mnt/disk2/targets.faa" in client.calls[0]["user_prompt"]
```

```python
def test_plan_from_message_rejects_seeded_bundle_signature_mismatch():
    bundle = InputBundle(
        bundle_type="seeded_proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/targets.faa"],
        seed_paths=["/mnt/disk2/cas_seed_queries.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    client = FakeLLMClient(
        {
            "assistant_message": "Planned the seeded proteins flow",
            "execution_plan": {
                "bundle_type": "seeded_proteins",
                "input_items": [
                    {
                        "bundle_type": "seeded_proteins",
                        "sample_id": "S01",
                        "input_paths": ["/mnt/disk2/targets.faa"],
                        "seed_paths": ["/mnt/disk2/other_seed.faa"],
                        "metadata": {},
                        "output_root": "/runs/S01",
                    }
                ],
                "stage_order": build_stage_order("seeded_proteins"),
                "parameter_overrides": {},
                "output_root": "/runs/S01",
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "Use the seeded proteins path",
            },
            "plan_warnings": [],
        }
    )

    result = plan_from_message("mine targets using the cas seeds", [bundle], client=client)

    assert result["execution_plan"].input_items == [bundle]
    assert result["plan_warnings"]
```

- [ ] **Step 2: Run the planner test file and confirm the new tests fail**

Run:

```bash
pytest tests/control_plane/test_planner.py -v
```

Expected:

- FAIL because the planner prompt does not include `seed_paths`
- FAIL because `_bundle_signature()` ignores `seed_paths`

- [ ] **Step 3: Update planner prompt generation and signature validation**

Replace the bundle signature and prompt helpers in `src/thermo_mining/control_plane/planner.py`:

```python
def _bundle_signature(bundle: InputBundle) -> tuple[str, str, tuple[str, ...], tuple[str, ...], str]:
    return (
        bundle.bundle_type,
        bundle.sample_id,
        tuple(bundle.input_paths),
        tuple(bundle.seed_paths),
        bundle.output_root,
    )


def _build_user_prompt(message: str, bundles: list[InputBundle]) -> str:
    lines = [
        "User request:",
        message,
        "",
        "Available input bundles:",
    ]
    for bundle in bundles:
        input_paths = ", ".join(bundle.input_paths)
        seed_paths = ", ".join(bundle.seed_paths) if bundle.seed_paths else "(none)"
        lines.extend(
            [
                f"- bundle_type: {bundle.bundle_type}",
                f"  sample_id: {bundle.sample_id}",
                f"  input_paths: {input_paths}",
                f"  seed_paths: {seed_paths}",
                f"  output_root: {bundle.output_root}",
            ]
        )
    return "\n".join(lines)
```

Do not change fallback planning behavior beyond using the updated bundle model. The existing `ExecutionPlan` fallback path should continue to round-trip `seed_paths` through `bundle.model_dump()`.

- [ ] **Step 4: Re-run planner tests**

Run:

```bash
pytest tests/control_plane/test_planner.py -v
```

Expected:

- PASS
- valid seeded plans survive model validation
- seeded prompt text exposes both target and seed paths

- [ ] **Step 5: Commit the planner changes**

Run:

```bash
git add tests/control_plane/test_planner.py src/thermo_mining/control_plane/planner.py
git commit -m "feat(planner): support seeded bundle prompts"
```

## Task 3: Implement Seed Sequence Recall

**Files:**
- Create: `src/thermo_mining/steps/seed_sequence_recall.py`
- Test: `tests/steps/test_seed_sequence_recall.py`

- [ ] **Step 1: Write failing tests for the seed sequence recall step**

Create `tests/steps/test_seed_sequence_recall.py`:

```python
import json
from pathlib import Path

from thermo_mining.steps.seed_sequence_recall import (
    build_seed_sequence_search_command,
    run_seed_sequence_recall_stage,
)


def test_build_seed_sequence_search_command_uses_mmseqs_easy_search(tmp_path):
    cmd = build_seed_sequence_search_command(
        mmseqs_bin="/opt/mmseqs/bin/mmseqs",
        seed_faa=tmp_path / "seed.faa",
        cluster_rep_faa=tmp_path / "cluster_rep_seq.fasta",
        output_tsv=tmp_path / "03_seed_sequence" / "raw.tsv",
        tmp_dir=tmp_path / "03_seed_sequence" / "tmp",
        min_seq_id=0.30,
        coverage=0.80,
        topk_per_seed=200,
    )

    assert cmd[:2] == ["/opt/mmseqs/bin/mmseqs", "easy-search"]
    assert cmd[2] == str(tmp_path / "seed.faa")
    assert cmd[3] == str(tmp_path / "cluster_rep_seq.fasta")
    assert "--min-seq-id" in cmd
    assert "--format-output" in cmd
    assert "query,target,pident" in cmd


def test_run_seed_sequence_recall_stage_writes_per_pair_hits(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1\nMSTNPKPQRK\n>target2\nAAAAAA\n", encoding="utf-8")

    def fake_run(cmd, check):
        output_tsv = Path(cmd[4])
        output_tsv.parent.mkdir(parents=True, exist_ok=True)
        output_tsv.write_text(
            "cas1\ttarget1\t88.0\ncas1\ttarget2\t44.5\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.seed_sequence_recall.subprocess.run", fake_run)

    result = run_seed_sequence_recall_stage(
        seed_faa=seed_faa,
        cluster_rep_faa=cluster_rep_faa,
        stage_dir=tmp_path / "03_seed_sequence",
        mmseqs_bin="/opt/mmseqs/bin/mmseqs",
        min_seq_id=0.30,
        coverage=0.80,
        topk_per_seed=200,
        software_version="test",
    )

    assert result["sequence_hits_tsv"] == tmp_path / "03_seed_sequence" / "sequence_hits.tsv"
    assert "target1\tcas1\t0.88" in result["sequence_hits_tsv"].read_text(encoding="utf-8")
    assert "target2\tcas1\t0.445" in result["sequence_hits_tsv"].read_text(encoding="utf-8")
    done = json.loads((tmp_path / "03_seed_sequence" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "03_seed_sequence_recall"
    assert done["retain_count"] == 2
```

- [ ] **Step 2: Run the new test file and confirm it fails**

Run:

```bash
pytest tests/steps/test_seed_sequence_recall.py -v
```

Expected:

- FAIL because `seed_sequence_recall.py` does not exist yet

- [ ] **Step 3: Implement `seed_sequence_recall.py`**

Create `src/thermo_mining/steps/seed_sequence_recall.py`:

```python
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def _combined_input_hash(*paths: str | Path) -> str:
    return "::".join(sha256_file(path) for path in paths)


def build_seed_sequence_search_command(
    mmseqs_bin: str,
    seed_faa: str | Path,
    cluster_rep_faa: str | Path,
    output_tsv: str | Path,
    tmp_dir: str | Path,
    min_seq_id: float,
    coverage: float,
    topk_per_seed: int,
) -> list[str]:
    return [
        mmseqs_bin,
        "easy-search",
        str(seed_faa),
        str(cluster_rep_faa),
        str(output_tsv),
        str(tmp_dir),
        "--min-seq-id",
        f"{min_seq_id:.2f}",
        "-c",
        f"{coverage:.2f}",
        "--cov-mode",
        "1",
        "--max-seqs",
        str(topk_per_seed),
        "--format-output",
        "query,target,pident",
    ]
```

```python
def run_seed_sequence_recall_stage(
    seed_faa: str | Path,
    cluster_rep_faa: str | Path,
    stage_dir: str | Path,
    mmseqs_bin: str,
    min_seq_id: float,
    coverage: float,
    topk_per_seed: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[str]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_tsv = stage_dir / "raw.tsv"
    tmp_dir = stage_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_seed_sequence_search_command(
        mmseqs_bin=mmseqs_bin,
        seed_faa=seed_faa,
        cluster_rep_faa=cluster_rep_faa,
        output_tsv=raw_tsv,
        tmp_dir=tmp_dir,
        min_seq_id=min_seq_id,
        coverage=coverage,
        topk_per_seed=topk_per_seed,
    )
    if dry_run:
        return {"command": cmd}

    subprocess.run(cmd, check=True)

    rows: list[dict[str, object]] = []
    for line in raw_tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        seed_id, target_id, pident = line.split("\t")
        rows.append(
            {
                "target_id": target_id,
                "seed_id": seed_id,
                "sequence_score": round(float(pident) / 100.0, 4),
            }
        )

    output_tsv = stage_dir / "sequence_hits.tsv"
    write_scores_tsv(output_tsv, rows, ["target_id", "seed_id", "sequence_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="03_seed_sequence_recall",
            input_hash=_combined_input_hash(seed_faa, cluster_rep_faa),
            parameters={
                "min_seq_id": min_seq_id,
                "coverage": coverage,
                "topk_per_seed": topk_per_seed,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"sequence_hits_tsv": output_tsv}
```

- [ ] **Step 4: Run the new seed-sequence tests**

Run:

```bash
pytest tests/steps/test_seed_sequence_recall.py -v
```

Expected:

- PASS
- the command uses `mmseqs easy-search`
- the stage writes one row per `(target_id, seed_id)` hit

- [ ] **Step 5: Commit the seed sequence recall step**

Run:

```bash
git add tests/steps/test_seed_sequence_recall.py src/thermo_mining/steps/seed_sequence_recall.py
git commit -m "feat(seed-recall): add sequence recall stage"
```

## Task 4: Implement Seed Structure Recall

**Files:**
- Create: `src/thermo_mining/steps/seed_structure_recall.py`
- Test: `tests/steps/test_seed_structure_recall.py`

- [ ] **Step 1: Write failing tests for structural seed recall**

Create `tests/steps/test_seed_structure_recall.py`:

```python
import json
from pathlib import Path

import pytest

from thermo_mining.steps.seed_structure_recall import (
    build_foldseek_createdb_command,
    run_seed_structure_recall_stage,
)


def test_build_foldseek_createdb_command_uses_local_binary(tmp_path):
    cmd = build_foldseek_createdb_command(
        foldseek_bin="/opt/foldseek/bin/foldseek",
        structures_dir=tmp_path / "target_structures",
        database_prefix=tmp_path / "target_db" / "db",
    )

    assert cmd == [
        "/opt/foldseek/bin/foldseek",
        "createdb",
        str(tmp_path / "target_structures"),
        str(tmp_path / "target_db" / "db"),
    ]


def test_run_seed_structure_recall_stage_fails_when_target_cap_is_exceeded(tmp_path):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1\nAAAA\n>target2\nCCCC\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="seed_structure_max_targets"):
        run_seed_structure_recall_stage(
            seed_faa=seed_faa,
            cluster_rep_faa=cluster_rep_faa,
            stage_dir=tmp_path / "04_seed_structure",
            colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
            colabfold_data_dir=Path("/srv/.cache/colabfold"),
            foldseek_bin="/opt/foldseek/bin/foldseek",
            msa_mode="single_sequence",
            num_models=1,
            num_recycle=1,
            min_tmscore=0.55,
            topk_per_seed=200,
            max_targets=1,
            software_version="test",
        )
```

```python
def test_run_seed_structure_recall_stage_writes_per_pair_scores(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1\nAAAAAA\n>target2\nGGGGGG\n", encoding="utf-8")

    def fake_run(cmd, check):
        if cmd[1] == "createdb":
            Path(cmd[3]).parent.mkdir(parents=True, exist_ok=True)
            return
        if cmd[1] == "easy-search":
            output_tsv = Path(cmd[4])
            output_tsv.parent.mkdir(parents=True, exist_ok=True)
            output_tsv.write_text(
                "seed_query\ttarget1\t0.81\nseed_query\ttarget2\t0.49\n",
                encoding="utf-8",
            )
            return

        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        query_faa = Path(cmd[-2])
        (output_dir / f"{query_faa.stem}_unrelaxed_rank_001_model_1.pdb").write_text(
            f"MODEL {query_faa.stem}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.seed_structure_recall.subprocess.run", fake_run)

    result = run_seed_structure_recall_stage(
        seed_faa=seed_faa,
        cluster_rep_faa=cluster_rep_faa,
        stage_dir=tmp_path / "04_seed_structure",
        colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
        colabfold_data_dir=Path("/srv/.cache/colabfold"),
        foldseek_bin="/opt/foldseek/bin/foldseek",
        msa_mode="single_sequence",
        num_models=1,
        num_recycle=1,
        min_tmscore=0.55,
        topk_per_seed=200,
        max_targets=50,
        software_version="test",
    )

    assert result["structure_hits_tsv"] == tmp_path / "04_seed_structure" / "structure_hits.tsv"
    assert "target1\tcas1\t0.81" in result["structure_hits_tsv"].read_text(encoding="utf-8")
    assert "target2" not in result["structure_hits_tsv"].read_text(encoding="utf-8")
    done = json.loads((tmp_path / "04_seed_structure" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "04_seed_structure_recall"
```

- [ ] **Step 2: Run the structural seed recall tests and confirm failure**

Run:

```bash
pytest tests/steps/test_seed_structure_recall.py -v
```

Expected:

- FAIL because `seed_structure_recall.py` does not exist yet

- [ ] **Step 3: Implement `seed_structure_recall.py`**

Create `src/thermo_mining/steps/seed_structure_recall.py`:

```python
import shutil
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_scores_tsv, write_fasta
from ..models import DoneRecord, ProteinRecord
from .foldseek_client import build_foldseek_easy_search_command
from .structure_predict import _select_output_pdb, build_colabfold_command


def _combined_input_hash(*paths: str | Path) -> str:
    return "::".join(sha256_file(path) for path in paths)


def build_foldseek_createdb_command(
    foldseek_bin: str,
    structures_dir: str | Path,
    database_prefix: str | Path,
) -> list[str]:
    return [foldseek_bin, "createdb", str(structures_dir), str(database_prefix)]
```

```python
def _predict_structure_manifest(
    input_faa: str | Path,
    query_root: Path,
    raw_root: Path,
    structures_root: Path,
    colabfold_batch_bin: str,
    colabfold_data_dir: str | Path,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    for record in read_fasta(input_faa):
        query_faa = query_root / f"{record.protein_id}.faa"
        raw_dir = raw_root / record.protein_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        write_fasta(query_faa, [ProteinRecord(record.protein_id, record.sequence, record.header)])
        subprocess.run(
            build_colabfold_command(
                colabfold_batch_bin=colabfold_batch_bin,
                data_dir=colabfold_data_dir,
                query_faa=query_faa,
                output_dir=raw_dir,
                msa_mode=msa_mode,
                num_models=num_models,
                num_recycle=num_recycle,
            ),
            check=True,
        )
        source_pdb = _select_output_pdb(raw_dir, record.protein_id)
        normalized_pdb = structures_root / f"{record.protein_id}.pdb"
        structures_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdb, normalized_pdb)
        manifest.append({"protein_id": record.protein_id, "pdb_path": str(normalized_pdb)})
    return manifest


def run_seed_structure_recall_stage(
    seed_faa: str | Path,
    cluster_rep_faa: str | Path,
    stage_dir: str | Path,
    colabfold_batch_bin: str,
    colabfold_data_dir: str | Path,
    foldseek_bin: str,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
    min_tmscore: float,
    topk_per_seed: int,
    max_targets: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[list[str]]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    target_records = read_fasta(cluster_rep_faa)
    if len(target_records) > max_targets:
        raise RuntimeError(
            f"seed_structure_max_targets exceeded: {len(target_records)} > {max_targets}"
        )

    seed_query_root = stage_dir / "seed_queries"
    seed_raw_root = stage_dir / "seed_raw"
    seed_structures_root = stage_dir / "seed_structures"
    target_query_root = stage_dir / "target_queries"
    target_raw_root = stage_dir / "target_raw"
    target_structures_root = stage_dir / "target_structures"
    target_db_prefix = stage_dir / "target_db" / "db"
    raw_hits_root = stage_dir / "raw"
    tmp_root = stage_dir / "tmp"

    commands: list[list[str]] = []

    if dry_run:
        seed_manifest = [
            {"protein_id": record.protein_id, "pdb_path": str(seed_structures_root / f"{record.protein_id}.pdb")}
            for record in read_fasta(seed_faa)
        ]
    else:
        seed_manifest = _predict_structure_manifest(
            input_faa=seed_faa,
            query_root=seed_query_root,
            raw_root=seed_raw_root,
            structures_root=seed_structures_root,
            colabfold_batch_bin=colabfold_batch_bin,
            colabfold_data_dir=colabfold_data_dir,
            msa_mode=msa_mode,
            num_models=num_models,
            num_recycle=num_recycle,
        )
        _predict_structure_manifest(
            input_faa=cluster_rep_faa,
            query_root=target_query_root,
            raw_root=target_raw_root,
            structures_root=target_structures_root,
            colabfold_batch_bin=colabfold_batch_bin,
            colabfold_data_dir=colabfold_data_dir,
            msa_mode=msa_mode,
            num_models=num_models,
            num_recycle=num_recycle,
        )
        createdb_cmd = build_foldseek_createdb_command(
            foldseek_bin=foldseek_bin,
            structures_dir=target_structures_root,
            database_prefix=target_db_prefix,
        )
        commands.append(createdb_cmd)
        subprocess.run(createdb_cmd, check=True)

    pair_scores: dict[tuple[str, str], float] = {}
    for seed_entry in seed_manifest:
        output_tsv = raw_hits_root / f"{seed_entry['protein_id']}.tsv"
        tmp_dir = tmp_root / seed_entry["protein_id"]
        cmd = build_foldseek_easy_search_command(
            foldseek_bin=foldseek_bin,
            query_pdb=seed_entry["pdb_path"],
            database_path=target_db_prefix,
            output_tsv=output_tsv,
            tmp_dir=tmp_dir,
            topk=topk_per_seed,
        )
        commands.append(cmd)
        if dry_run:
            continue
        subprocess.run(cmd, check=True)
        for line in output_tsv.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            _, target_id, alntmscore = line.split("\t")
            score = float(alntmscore)
            if score < min_tmscore:
                continue
            pair_key = (Path(target_id).stem, seed_entry["protein_id"])
            pair_scores[pair_key] = max(pair_scores.get(pair_key, 0.0), round(score, 4))

    if dry_run:
        return {"commands": commands}

    rows = [
        {
            "target_id": target_id,
            "seed_id": seed_id,
            "structure_score": score,
        }
        for (target_id, seed_id), score in sorted(pair_scores.items())
    ]
    output_tsv = stage_dir / "structure_hits.tsv"
    write_scores_tsv(output_tsv, rows, ["target_id", "seed_id", "structure_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="04_seed_structure_recall",
            input_hash=_combined_input_hash(seed_faa, cluster_rep_faa),
            parameters={
                "min_tmscore": min_tmscore,
                "topk_per_seed": topk_per_seed,
                "max_targets": max_targets,
                "msa_mode": msa_mode,
                "num_models": num_models,
                "num_recycle": num_recycle,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"structure_hits_tsv": output_tsv}
```

- [ ] **Step 4: Run the new structural recall tests**

Run:

```bash
pytest tests/steps/test_seed_structure_recall.py -v
```

Expected:

- PASS
- the stage fails before any structure prediction when `max_targets` is exceeded
- the stage writes only hits that survive the structural TM-score floor

- [ ] **Step 5: Commit the structural recall stage**

Run:

```bash
git add tests/steps/test_seed_structure_recall.py src/thermo_mining/steps/seed_structure_recall.py
git commit -m "feat(seed-recall): add structure recall stage"
```

## Task 5: Merge Seed Hits And Extend Reporting

**Files:**
- Create: `src/thermo_mining/steps/seed_recall_merge.py`
- Modify: `src/thermo_mining/steps/rerank.py`
- Modify: `src/thermo_mining/reporting.py`
- Create: `tests/steps/test_seed_recall_merge.py`
- Modify: `tests/steps/test_rerank.py`

- [ ] **Step 1: Write failing merge and reporting tests**

Create `tests/steps/test_seed_recall_merge.py`:

```python
import json

from thermo_mining.steps.seed_recall_merge import run_seed_recall_merge_stage


def test_run_seed_recall_merge_stage_unions_hits_and_writes_seeded_targets(tmp_path):
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1 desc\nAAAA\n>target2\nCCCC\n>target3\nGGGG\n", encoding="utf-8")
    sequence_hits_tsv = tmp_path / "sequence_hits.tsv"
    sequence_hits_tsv.write_text(
        "target_id\tseed_id\tsequence_score\n"
        "target1\tcas1\t0.91\n"
        "target2\tcas1\t0.72\n",
        encoding="utf-8",
    )
    structure_hits_tsv = tmp_path / "structure_hits.tsv"
    structure_hits_tsv.write_text(
        "target_id\tseed_id\tstructure_score\n"
        "target2\tcas2\t0.81\n"
        "target3\tcas1\t0.77\n",
        encoding="utf-8",
    )

    result = run_seed_recall_merge_stage(
        cluster_rep_faa=cluster_rep_faa,
        sequence_hits_tsv=sequence_hits_tsv,
        structure_hits_tsv=structure_hits_tsv,
        stage_dir=tmp_path / "05_seed_merge",
        software_version="test",
    )

    manifest_text = result["seed_manifest_tsv"].read_text(encoding="utf-8")
    assert "target1\tcas1\tsequence\t0.91\t0.0" in manifest_text
    assert "target2\tcas1;cas2\tboth\t0.72\t0.81" in manifest_text
    assert "target3\tcas1\tstructure\t0.0\t0.77" in manifest_text
    seeded_targets_text = result["seeded_targets_faa"].read_text(encoding="utf-8")
    assert ">target1 desc" in seeded_targets_text
    assert ">target3" in seeded_targets_text
    done = json.loads((tmp_path / "05_seed_merge" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "05_seed_recall_merge"
```

Append these tests to `tests/steps/test_rerank.py`:

```python
def test_combine_stage_scores_merges_seed_provenance_without_changing_formula():
    combined = combine_stage_scores(
        thermo_rows=[{"protein_id": "p1", "thermo_score": 0.9}],
        protrek_rows=[{"protein_id": "p1", "protrek_score": 0.8}],
        foldseek_rows=[{"protein_id": "p1", "foldseek_score": 0.6}],
        hot_spring_ids={"p1"},
        seed_rows=[
            {
                "target_id": "p1",
                "seed_ids": "cas1;cas2",
                "seed_channels": "both",
                "best_sequence_score": 0.91,
                "best_structure_score": 0.84,
            }
        ],
    )

    assert combined[0]["seed_ids"] == "cas1;cas2"
    assert combined[0]["seed_channels"] == "both"
    assert combined[0]["best_sequence_score"] == 0.91
    assert combined[0]["best_structure_score"] == 0.84
    assert combined[0]["final_score"] == 0.82
```

```python
def test_write_report_outputs_writes_seed_columns_and_empty_headers(tmp_path):
    outputs = write_report_outputs(tmp_path, "run_001", [])

    top_100_text = outputs["top_100_tsv"].read_text(encoding="utf-8")
    assert top_100_text.startswith(
        "protein_id\tseed_ids\tseed_channels\tbest_sequence_score\tbest_structure_score\tthermo_score"
    )
    assert "Tier 1: 0" in outputs["summary_md"].read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the merge/report tests and confirm failure**

Run:

```bash
pytest tests/steps/test_seed_recall_merge.py tests/steps/test_rerank.py -v
```

Expected:

- FAIL because `seed_recall_merge.py` does not exist yet
- FAIL because `combine_stage_scores()` does not accept `seed_rows`
- FAIL because report headers do not yet include seed columns

- [ ] **Step 3: Implement merge, seed-aware reranking, and report schema**

Create `src/thermo_mining/steps/seed_recall_merge.py`:

```python
import csv
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord


def _combined_input_hash(*paths: str | Path) -> str:
    return "::".join(sha256_file(path) for path in paths)


def _read_hits(path: str | Path, score_field: str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def run_seed_recall_merge_stage(
    cluster_rep_faa: str | Path,
    sequence_hits_tsv: str | Path,
    structure_hits_tsv: str | Path,
    stage_dir: str | Path,
    software_version: str,
) -> dict[str, object]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    target_records = {record.protein_id: record for record in read_fasta(cluster_rep_faa)}
    merged: dict[str, dict[str, object]] = {}

    for row in _read_hits(sequence_hits_tsv, "sequence_score"):
        entry = merged.setdefault(
            row["target_id"],
            {
                "target_id": row["target_id"],
                "seed_ids": set(),
                "seed_channels": set(),
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        entry["seed_ids"].add(row["seed_id"])
        entry["seed_channels"].add("sequence")
        entry["best_sequence_score"] = max(entry["best_sequence_score"], float(row["sequence_score"]))

    for row in _read_hits(structure_hits_tsv, "structure_score"):
        entry = merged.setdefault(
            row["target_id"],
            {
                "target_id": row["target_id"],
                "seed_ids": set(),
                "seed_channels": set(),
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        entry["seed_ids"].add(row["seed_id"])
        entry["seed_channels"].add("structure")
        entry["best_structure_score"] = max(entry["best_structure_score"], float(row["structure_score"]))

    manifest_rows: list[dict[str, object]] = []
    retained_records = []
    for target_id in sorted(merged):
        if target_id not in target_records:
            raise RuntimeError(f"seed recall merge referenced unknown target '{target_id}'")
        channels = merged[target_id]["seed_channels"]
        if channels == {"sequence", "structure"}:
            channel_label = "both"
        elif channels == {"sequence"}:
            channel_label = "sequence"
        else:
            channel_label = "structure"
        manifest_rows.append(
            {
                "target_id": target_id,
                "seed_ids": ";".join(sorted(merged[target_id]["seed_ids"])),
                "seed_channels": channel_label,
                "best_sequence_score": round(float(merged[target_id]["best_sequence_score"]), 4),
                "best_structure_score": round(float(merged[target_id]["best_structure_score"]), 4),
            }
        )
        retained_records.append(target_records[target_id])

    seed_manifest_tsv = stage_dir / "seed_manifest.tsv"
    seeded_targets_faa = stage_dir / "seeded_targets.faa"
    write_scores_tsv(
        seed_manifest_tsv,
        manifest_rows,
        ["target_id", "seed_ids", "seed_channels", "best_sequence_score", "best_structure_score"],
    )
    write_fasta(seeded_targets_faa, retained_records)
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="05_seed_recall_merge",
            input_hash=_combined_input_hash(cluster_rep_faa, sequence_hits_tsv, structure_hits_tsv),
            parameters={},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(manifest_rows),
            reject_count=0,
        ),
    )
    return {
        "seed_manifest_tsv": seed_manifest_tsv,
        "seeded_targets_faa": seeded_targets_faa,
        "seed_rows": manifest_rows,
    }
```

Update `src/thermo_mining/steps/rerank.py`:

```python
def combine_stage_scores(
    thermo_rows: list[dict[str, object]],
    protrek_rows: list[dict[str, object]],
    foldseek_rows: list[dict[str, object]],
    hot_spring_ids: set[str],
    seed_rows: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    thermo_map = {row["protein_id"]: float(row["thermo_score"]) for row in thermo_rows}
    protrek_map = {row["protein_id"]: float(row["protrek_score"]) for row in protrek_rows}
    foldseek_map = {row["protein_id"]: float(row["foldseek_score"]) for row in foldseek_rows}
    seed_map = {
        str(row["target_id"]): {
            "seed_ids": str(row["seed_ids"]),
            "seed_channels": str(row["seed_channels"]),
            "best_sequence_score": float(row["best_sequence_score"]),
            "best_structure_score": float(row["best_structure_score"]),
        }
        for row in (seed_rows or [])
    }
    all_ids = sorted(set(thermo_map) | set(protrek_map) | set(foldseek_map))

    combined: list[dict[str, object]] = []
    for protein_id in all_ids:
        seed_support = seed_map.get(
            protein_id,
            {
                "seed_ids": "",
                "seed_channels": "",
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        thermo_score = thermo_map.get(protein_id, 0.0)
        protrek_score = protrek_map.get(protein_id, 0.0)
        foldseek_score = foldseek_map.get(protein_id, 0.0)
        origin_bonus = 0.05 if protein_id in hot_spring_ids else 0.0
        final_score = round(
            thermo_score * 0.35 + protrek_score * 0.35 + foldseek_score * 0.25 + origin_bonus,
            4,
        )
        combined.append(
            {
                "protein_id": protein_id,
                "seed_ids": seed_support["seed_ids"],
                "seed_channels": seed_support["seed_channels"],
                "best_sequence_score": seed_support["best_sequence_score"],
                "best_structure_score": seed_support["best_structure_score"],
                "thermo_score": thermo_score,
                "protrek_score": protrek_score,
                "foldseek_score": foldseek_score,
                "origin_bonus": origin_bonus,
                "final_score": final_score,
                "tier": assign_tier(final_score),
            }
        )
    return sorted(combined, key=lambda row: row["final_score"], reverse=True)
```

Update `src/thermo_mining/reporting.py`:

```python
REPORT_FIELDNAMES = [
    "protein_id",
    "seed_ids",
    "seed_channels",
    "best_sequence_score",
    "best_structure_score",
    "thermo_score",
    "protrek_score",
    "foldseek_score",
    "origin_bonus",
    "final_score",
    "tier",
]
```

Do not special-case empty rows in `write_report_outputs()`. `write_scores_tsv()` already writes headers for empty lists, and `build_summary_markdown()` already produces zero counts when `tier_counts` is empty.

- [ ] **Step 4: Re-run merge/report tests**

Run:

```bash
pytest tests/steps/test_seed_recall_merge.py tests/steps/test_rerank.py -v
```

Expected:

- PASS
- merged seed rows use union semantics and deterministic channel labels
- reports always expose the seed columns even when there are no rows

- [ ] **Step 5: Commit the merge/report changes**

Run:

```bash
git add tests/steps/test_seed_recall_merge.py tests/steps/test_rerank.py src/thermo_mining/steps/seed_recall_merge.py src/thermo_mining/steps/rerank.py src/thermo_mining/reporting.py
git commit -m "feat(seed-recall): merge seed hits into reports"
```

## Task 6: Add The Seeded CLI Pipeline

**Files:**
- Modify: `src/thermo_mining/cli.py`
- Modify: `src/thermo_mining/pipeline.py`
- Test: `tests/test_pipeline_cli.py`

- [ ] **Step 1: Write failing seeded CLI and pipeline tests**

Append these tests to `tests/test_pipeline_cli.py`:

```python
def test_run_seeded_pipeline_executes_seed_recall_before_thermo_stages(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        f"""
runtime:
  runs_root: {tmp_path.as_posix()}/runs
defaults:
  seed_sequence_min_seq_id: 0.30
  seed_sequence_coverage: 0.80
  seed_sequence_topk_per_seed: 200
  seed_structure_min_tmscore: 0.55
  seed_structure_topk_per_seed: 200
  seed_structure_max_targets: 500
  prefilter_min_length: 80
  prefilter_max_length: 1200
  prefilter_max_single_residue_fraction: 0.7
  cluster_min_seq_id: 0.9
  cluster_coverage: 0.8
  cluster_threads: 64
  thermo_top_fraction: 0.1
  thermo_min_score: 0.5
  protrek_query_texts:
    - thermostable enzyme
  protrek_batch_size: 8
  protrek_top_k: 50
  colabfold_msa_mode: single_sequence
  colabfold_num_models: 1
  colabfold_num_recycle: 1
  foldseek_topk: 5
  foldseek_min_tmscore: 0.6
tools:
  mmseqs_bin: /opt/mmseqs/bin/mmseqs
  conda_bin: /opt/miniconda/bin/conda
  temstapro_bin: /opt/temstapro/bin/temstapro
  temstapro_conda_env_name: temstapro_env_CPU
  temstapro_repo_root: /srv/TemStaPro-main
  temstapro_model_dir: /srv/TemStaPro-main/models
  temstapro_cache_dir: /srv/TemStaPro-main/cache
  temstapro_hf_home: /srv/.cache/huggingface
  temstapro_transformers_offline: true
  protrek_python_bin: /opt/protrek/bin/python
  protrek_repo_root: /srv/ProTrek
  protrek_weights_dir: /srv/ProTrek/ProTrek_650M.pt
  colabfold_batch_bin: /opt/colabfold/bin/colabfold_batch
  colabfold_data_dir: /srv/.cache/colabfold
  foldseek_bin: /opt/foldseek/bin/foldseek
  foldseek_database_path: /srv/foldseek/db/afdb50
""".strip(),
        encoding="utf-8",
    )
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
```

```python
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: calls.append("cluster") or {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: calls.append("seed_sequence") or {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: calls.append("seed_structure") or {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: calls.append("seed_merge")
        or {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": tmp_path / "seeded_targets.faa",
            "seed_rows": [
                {
                    "target_id": "target1",
                    "seed_ids": "cas1",
                    "seed_channels": "both",
                    "best_sequence_score": 0.9,
                    "best_structure_score": 0.8,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_temstapro_screen",
        lambda **kwargs: calls.append("thermo") or {"thermo_hits_faa": target_faa, "thermo_scores_tsv": tmp_path / "thermo.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_structure_predict_stage",
        lambda **kwargs: calls.append("structure")
        or {
            "structure_manifest": [{"protein_id": "target1", "pdb_path": str(tmp_path / "p1.pdb")}],
            "structure_manifest_json": tmp_path / "structure_manifest.json",
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline._read_scores_tsv",
        lambda path: [{"protein_id": "target1", "thermo_score": "0.9", "protrek_score": "0.8", "foldseek_score": "0.7"}],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: calls.append("report") or {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_demo",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=False,
    )

    assert calls == [
        "prefilter",
        "cluster",
        "seed_sequence",
        "seed_structure",
        "seed_merge",
        "thermo",
        "protrek",
        "structure",
        "foldseek",
        "report",
    ]


def test_run_seeded_pipeline_short_circuits_when_merge_is_empty(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(f"runtime:\n  runs_root: {tmp_path.as_posix()}/runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: calls.append("cluster") or {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: calls.append("seed_sequence") or {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: calls.append("seed_structure") or {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: calls.append("seed_merge")
        or {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": tmp_path / "seeded_targets.faa",
            "seed_rows": [],
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: calls.append(("report", rows)) or {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_empty",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=False,
    )

    assert calls == [
        "prefilter",
        "cluster",
        "seed_sequence",
        "seed_structure",
        "seed_merge",
        ("report", []),
    ]
```

```python
def test_run_seeded_pipeline_skips_seed_sequence_stage_when_resume_hash_matches(tmp_path, monkeypatch):
    import json

    from thermo_mining.io_utils import sha256_file

    config_path = tmp_path / "platform.yaml"
    config_path.write_text(f"runtime:\n  runs_root: {tmp_path.as_posix()}/runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    run_root = tmp_path / "runs" / "seeded_resume"
    stage_dirs = build_stage_dirs(run_root, build_stage_order("seeded_proteins"))
    stage_dirs["seed_sequence_recall"].mkdir(parents=True, exist_ok=True)
    (stage_dirs["seed_sequence_recall"] / "sequence_hits.tsv").write_text(
        "target_id\tseed_id\tsequence_score\ntarget1\tcas1\t0.9\n",
        encoding="utf-8",
    )
    (stage_dirs["seed_sequence_recall"] / "DONE.json").write_text(
        json.dumps(
            {
                "stage_name": "03_seed_sequence_recall",
                "input_hash": f"{sha256_file(seed_faa)}::{sha256_file(target_faa)}",
                "parameters": {},
                "software_version": "test",
                "runtime_seconds": 0.1,
                "retain_count": 1,
                "reject_count": 0,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("seed sequence stage should have been skipped")),
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: {"seed_manifest_tsv": tmp_path / "seed_manifest.tsv", "seeded_targets_faa": tmp_path / "seeded_targets.faa", "seed_rows": []},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_resume",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=True,
    )


def test_cli_main_dispatches_run_seeded_pipeline(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("runtime:\n  runs_root: runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    captured = {}

    monkeypatch.setattr("thermo_mining.cli.run_seeded_pipeline", lambda **kwargs: captured.update(kwargs) or {"summary_md": tmp_path / "summary.md"})

    main(
        [
            "run-seeded",
            "--config",
            str(config_path),
            "--run-name",
            "seeded_demo",
            "--seed-faa",
            str(seed_faa),
            "--target-faa",
            str(target_faa),
            "--resume",
        ]
    )

    assert captured["config_path"] == config_path
    assert captured["run_name"] == "seeded_demo"
    assert captured["seed_faa"] == seed_faa
    assert captured["target_faa"] == target_faa
    assert captured["resume"] is True
```

- [ ] **Step 2: Run the CLI pipeline tests and confirm failure**

Run:

```bash
pytest tests/test_pipeline_cli.py -v
```

Expected:

- FAIL because `run_seeded_pipeline()` does not exist
- FAIL because the CLI has no `run-seeded` subcommand

- [ ] **Step 3: Implement `run_seeded_pipeline()` and CLI dispatch**

Update `src/thermo_mining/pipeline.py` imports:

```python
from .steps.seed_recall_merge import run_seed_recall_merge_stage
from .steps.seed_sequence_recall import run_seed_sequence_recall_stage
from .steps.seed_structure_recall import run_seed_structure_recall_stage
```

Add this helper above `run_seeded_pipeline()`:

```python
def _combined_resume_hash(*paths: str | Path) -> str:
    return "::".join(sha256_file(path) for path in paths)
```

Add this new seeded entry point to `src/thermo_mining/pipeline.py`:

```python
def run_seeded_pipeline(
    config_path: str | Path,
    run_name: str,
    seed_faa: str | Path,
    target_faa: str | Path,
    resume: bool = False,
) -> dict[str, Path]:
    settings = load_settings(config_path)
    stage_order = build_stage_order("seeded_proteins")
    run_root = Path(settings.runtime.runs_root) / run_name
    stage_dirs = build_stage_dirs(run_root, stage_order)
    seed_faa = Path(seed_faa)
    target_faa = Path(target_faa)

    prefilter_done = stage_dirs["prefilter"] / "DONE.json"
    if should_skip_stage(prefilter_done, sha256_file(target_faa), resume):
        prefilter_result = {"filtered_faa": stage_dirs["prefilter"] / "filtered.faa"}
    else:
        prefilter_result = run_prefilter(
            input_faa=target_faa,
            stage_dir=stage_dirs["prefilter"],
            min_length=settings.defaults.prefilter_min_length,
            max_length=settings.defaults.prefilter_max_length,
            max_single_residue_fraction=settings.defaults.prefilter_max_single_residue_fraction,
            software_version=__version__,
        )
    cluster_input = Path(prefilter_result["filtered_faa"])
    cluster_done = stage_dirs["mmseqs_cluster"] / "DONE.json"
    if should_skip_stage(cluster_done, sha256_file(cluster_input), resume):
        cluster_result = {
            "cluster_rep_faa": stage_dirs["mmseqs_cluster"] / "cluster_rep_seq.fasta",
            "cluster_membership_tsv": stage_dirs["mmseqs_cluster"] / "cluster_cluster.tsv",
        }
    else:
        cluster_result = run_mmseqs_cluster(
            input_faa=cluster_input,
            stage_dir=stage_dirs["mmseqs_cluster"],
            mmseqs_bin=settings.tools.mmseqs_bin,
            min_seq_id=settings.defaults.cluster_min_seq_id,
            coverage=settings.defaults.cluster_coverage,
            threads=settings.defaults.cluster_threads,
            software_version=__version__,
        )
    cluster_rep_faa = Path(cluster_result["cluster_rep_faa"])

    sequence_done = stage_dirs["seed_sequence_recall"] / "DONE.json"
    sequence_hash = _combined_resume_hash(seed_faa, cluster_rep_faa)
    if should_skip_stage(sequence_done, sequence_hash, resume):
        sequence_result = {"sequence_hits_tsv": stage_dirs["seed_sequence_recall"] / "sequence_hits.tsv"}
    else:
        sequence_result = run_seed_sequence_recall_stage(
            seed_faa=seed_faa,
            cluster_rep_faa=cluster_rep_faa,
            stage_dir=stage_dirs["seed_sequence_recall"],
            mmseqs_bin=settings.tools.mmseqs_bin,
            min_seq_id=settings.defaults.seed_sequence_min_seq_id,
            coverage=settings.defaults.seed_sequence_coverage,
            topk_per_seed=settings.defaults.seed_sequence_topk_per_seed,
            software_version=__version__,
        )

    structure_done = stage_dirs["seed_structure_recall"] / "DONE.json"
    structure_hash = _combined_resume_hash(seed_faa, cluster_rep_faa)
    if should_skip_stage(structure_done, structure_hash, resume):
        structure_result = {"structure_hits_tsv": stage_dirs["seed_structure_recall"] / "structure_hits.tsv"}
    else:
        structure_result = run_seed_structure_recall_stage(
            seed_faa=seed_faa,
            cluster_rep_faa=cluster_rep_faa,
            stage_dir=stage_dirs["seed_structure_recall"],
            colabfold_batch_bin=settings.tools.colabfold_batch_bin,
            colabfold_data_dir=settings.tools.colabfold_data_dir,
            foldseek_bin=settings.tools.foldseek_bin,
            msa_mode=settings.defaults.colabfold_msa_mode,
            num_models=settings.defaults.colabfold_num_models,
            num_recycle=settings.defaults.colabfold_num_recycle,
            min_tmscore=settings.defaults.seed_structure_min_tmscore,
            topk_per_seed=settings.defaults.seed_structure_topk_per_seed,
            max_targets=settings.defaults.seed_structure_max_targets,
            software_version=__version__,
        )

    merge_done = stage_dirs["seed_recall_merge"] / "DONE.json"
    seed_manifest_tsv = stage_dirs["seed_recall_merge"] / "seed_manifest.tsv"
    seeded_targets_faa = stage_dirs["seed_recall_merge"] / "seeded_targets.faa"
    merge_hash = _combined_resume_hash(cluster_rep_faa, sequence_result["sequence_hits_tsv"], structure_result["structure_hits_tsv"])
    if should_skip_stage(merge_done, merge_hash, resume) and seed_manifest_tsv.exists():
        merge_result = {
            "seed_manifest_tsv": seed_manifest_tsv,
            "seeded_targets_faa": seeded_targets_faa,
            "seed_rows": _read_scores_tsv(seed_manifest_tsv),
        }
    else:
        merge_result = run_seed_recall_merge_stage(
            cluster_rep_faa=cluster_rep_faa,
            sequence_hits_tsv=sequence_result["sequence_hits_tsv"],
            structure_hits_tsv=structure_result["structure_hits_tsv"],
            stage_dir=stage_dirs["seed_recall_merge"],
            software_version=__version__,
        )

    if not merge_result["seed_rows"]:
        return write_report_outputs(stage_dirs["rerank_report"], run_name, [])

    thermo_result = run_temstapro_screen(
        input_faa=Path(merge_result["seeded_targets_faa"]),
        stage_dir=stage_dirs["temstapro_screen"],
        conda_bin=settings.tools.conda_bin,
        conda_env_name=settings.tools.temstapro_conda_env_name,
        temstapro_bin=settings.tools.temstapro_bin,
        repo_root=settings.tools.temstapro_repo_root,
        model_dir=settings.tools.temstapro_model_dir,
        cache_dir=settings.tools.temstapro_cache_dir,
        hf_home=settings.tools.temstapro_hf_home,
        transformers_offline=settings.tools.temstapro_transformers_offline,
        top_fraction=settings.defaults.thermo_top_fraction,
        min_score=settings.defaults.thermo_min_score,
        software_version=__version__,
    )
    protrek_result = run_protrek_stage(
        input_faa=Path(thermo_result["thermo_hits_faa"]),
        stage_dir=stage_dirs["protrek_recall"],
        python_bin=settings.tools.protrek_python_bin,
        index_script="scripts/protrek_build_index.py",
        query_script="scripts/protrek_query.py",
        repo_root=settings.tools.protrek_repo_root,
        weights_dir=settings.tools.protrek_weights_dir,
        query_texts=list(settings.defaults.protrek_query_texts),
        batch_size=settings.defaults.protrek_batch_size,
        top_k=settings.defaults.protrek_top_k,
        software_version=__version__,
    )
    final_structure_result = run_structure_predict_stage(
        input_faa=Path(thermo_result["thermo_hits_faa"]),
        stage_dir=stage_dirs["structure_predict"],
        colabfold_batch_bin=settings.tools.colabfold_batch_bin,
        colabfold_data_dir=settings.tools.colabfold_data_dir,
        msa_mode=settings.defaults.colabfold_msa_mode,
        num_models=settings.defaults.colabfold_num_models,
        num_recycle=settings.defaults.colabfold_num_recycle,
        software_version=__version__,
    )
    foldseek_result = run_foldseek_stage(
        structure_manifest=list(final_structure_result["structure_manifest"]),
        stage_dir=stage_dirs["foldseek_confirm"],
        foldseek_bin=settings.tools.foldseek_bin,
        database_path=settings.tools.foldseek_database_path,
        topk=settings.defaults.foldseek_topk,
        min_tmscore=settings.defaults.foldseek_min_tmscore,
        software_version=__version__,
    )

    combined_rows = combine_stage_scores(
        thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
        protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
        foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
        hot_spring_ids={record.protein_id for record in read_fasta(target_faa)},
        seed_rows=list(merge_result["seed_rows"]),
    )
    return write_report_outputs(stage_dirs["rerank_report"], run_name, combined_rows)
```

Update `src/thermo_mining/cli.py`:

```python
from .pipeline import run_pipeline, run_seeded_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thermo-mining")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--run-name", required=True)
    run_parser.add_argument("--input-faa", required=True)
    run_parser.add_argument("--resume", action="store_true")

    run_seeded_parser = subparsers.add_parser("run-seeded")
    run_seeded_parser.add_argument("--config", required=True)
    run_seeded_parser.add_argument("--run-name", required=True)
    run_seeded_parser.add_argument("--seed-faa", required=True)
    run_seeded_parser.add_argument("--target-faa", required=True)
    run_seeded_parser.add_argument("--resume", action="store_true")
```

Extend `main()`:

```python
    if args.command == "run-seeded":
        return run_seeded_pipeline(
            config_path=Path(args.config),
            run_name=args.run_name,
            seed_faa=Path(args.seed_faa),
            target_faa=Path(args.target_faa),
            resume=args.resume,
        )
    if args.command != "run":
        return None
```

After the new seed-stage guards are in place, mirror the existing `should_skip_stage(...)` pattern for the downstream `temstapro_screen`, `protrek_recall`, and `structure_predict` stages using the same file names already used by `run_pipeline()`. Do not weaken resume semantics for the seeded mode.

- [ ] **Step 4: Re-run the CLI pipeline tests**

Run:

```bash
pytest tests/test_pipeline_cli.py -v
```

Expected:

- PASS
- `run-seeded` dispatches into the seeded pipeline entry point
- seed recall stages execute before thermo scoring
- empty merged recall writes an empty report and skips downstream stages

- [ ] **Step 5: Commit the seeded CLI pipeline**

Run:

```bash
git add tests/test_pipeline_cli.py src/thermo_mining/cli.py src/thermo_mining/pipeline.py
git commit -m "feat(seed-pipeline): add seeded cli runtime"
```

## Task 7: Integrate Seeded Runs Into The Control-Plane Runner

**Files:**
- Modify: `src/thermo_mining/control_plane/runner.py`
- Modify: `tests/control_plane/test_runner.py`

- [ ] **Step 1: Write failing seeded runner tests**

Update `_make_plan()` in `tests/control_plane/test_runner.py` so it can create seeded plans:

```python
def _make_plan(
    bundle_type: str,
    input_paths: list[str],
    output_root: str,
    overrides: dict[str, object] | None = None,
    seed_paths: list[str] | None = None,
) -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type=bundle_type,
        sample_id="S01",
        input_paths=input_paths,
        seed_paths=seed_paths or [],
        metadata={},
        output_root=output_root,
    )
    return ExecutionPlan(
        bundle_type=bundle_type,
        input_items=[bundle],
        stage_order=build_stage_order(bundle_type),
        parameter_overrides=overrides or {},
        output_root=output_root,
        resume_policy="if_possible",
        explanation="test",
    )
```

Append these tests:

```python
def test_run_job_executes_seeded_stage_order(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    plan = _make_plan(
        "seeded_proteins",
        [str(target_faa)],
        "/runs/S01",
        seed_paths=[str(seed_faa)],
    )
    record = create_pending_run(tmp_path, plan)
    calls = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_sequence_recall_stage",
        lambda **kwargs: calls.append("seed_sequence") or {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_structure_recall_stage",
        lambda **kwargs: calls.append("seed_structure") or {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_recall_merge_stage",
        lambda **kwargs: calls.append("seed_merge")
        or {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": target_faa,
            "seed_rows": [
                {
                    "target_id": "target1",
                    "seed_ids": "cas1",
                    "seed_channels": "both",
                    "best_sequence_score": 0.9,
                    "best_structure_score": 0.8,
                }
            ],
        },
    )
```

```python
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_temstapro_screen",
        lambda **kwargs: (
            calls.append("temstapro"),
            (tmp_path / "hits.faa").write_text(">target1\nAAAAAA\n", encoding="utf-8"),
            {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_structure_predict_stage",
        lambda **kwargs: calls.append("structure")
        or {
            "structure_manifest": [{"protein_id": "target1", "pdb_path": str(tmp_path / "p1.pdb")}],
            "structure_manifest_json": tmp_path / "structure_manifest.json",
        },
        raising=False,
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner._read_scores_tsv",
        lambda path: [{"protein_id": "target1", "thermo_score": "0.9", "protrek_score": "0.8", "foldseek_score": "0.7"}],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.combine_stage_scores",
        lambda **kwargs: [
            {
                "protein_id": "target1",
                "seed_ids": "cas1",
                "seed_channels": "both",
                "best_sequence_score": 0.9,
                "best_structure_score": 0.8,
                "thermo_score": 0.9,
                "protrek_score": 0.8,
                "foldseek_score": 0.7,
                "origin_bonus": 0.05,
                "final_score": 0.82,
                "tier": "Tier 1",
            }
        ],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.write_report_outputs",
        lambda stage_dir, *args, **kwargs: calls.append("report") or {"summary_md": tmp_path / "summary.md"},
    )

    run_job(record.run_dir)

    assert calls == [
        "prefilter",
        "mmseqs",
        "seed_sequence",
        "seed_structure",
        "seed_merge",
        "temstapro",
        "protrek",
        "structure",
        "foldseek",
        "report",
    ]
```

```python
def test_run_job_short_circuits_seeded_runs_when_no_seed_hits_survive(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    plan = _make_plan(
        "seeded_proteins",
        [str(target_faa)],
        "/runs/S01",
        seed_paths=[str(seed_faa)],
    )
    record = create_pending_run(tmp_path, plan)
    calls = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_sequence_recall_stage",
        lambda **kwargs: calls.append("seed_sequence") or {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_structure_recall_stage",
        lambda **kwargs: calls.append("seed_structure") or {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_seed_recall_merge_stage",
        lambda **kwargs: calls.append("seed_merge")
        or {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": tmp_path / "seeded_targets.faa",
            "seed_rows": [],
        },
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.write_report_outputs",
        lambda stage_dir, *args, **kwargs: calls.append("report") or {"summary_md": tmp_path / "summary.md"},
    )

    run_job(record.run_dir)

    assert calls == ["prefilter", "mmseqs", "seed_sequence", "seed_structure", "seed_merge", "report"]
```

- [ ] **Step 2: Run the runner tests and confirm failure**

Run:

```bash
pytest tests/control_plane/test_runner.py -v
```

Expected:

- FAIL because `run_job()` has no branches for the three new seed stages
- FAIL because the runner does not know how to skip downstream thermo stages after an empty seed merge

- [ ] **Step 3: Implement seeded runner integration**

Update `src/thermo_mining/control_plane/runner.py` imports:

```python
from thermo_mining.steps.seed_recall_merge import run_seed_recall_merge_stage
from thermo_mining.steps.seed_sequence_recall import run_seed_sequence_recall_stage
from thermo_mining.steps.seed_structure_recall import run_seed_structure_recall_stage
```

Then extend `run_job()` with seeded state:

```python
    current_input = Path(bundle["input_paths"][0])
    seed_input = Path(bundle["seed_paths"][0]) if bundle["bundle_type"] == "seeded_proteins" else None
    seeded_merge_rows: list[dict[str, object]] = []
    skip_downstream_for_empty_seeded_run = False
```

Add new stage branches inside the loop:

```python
            elif stage_name == "seed_sequence_recall":
                if seed_input is None:
                    raise RuntimeError("seed_sequence_recall stage requires a seed input")
                sequence_result = run_seed_sequence_recall_stage(
                    seed_faa=seed_input,
                    cluster_rep_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    mmseqs_bin=settings.tools.mmseqs_bin,
                    min_seq_id=float(_plan_override(plan, "seed_sequence_min_seq_id", settings.defaults.seed_sequence_min_seq_id)),
                    coverage=float(_plan_override(plan, "seed_sequence_coverage", settings.defaults.seed_sequence_coverage)),
                    topk_per_seed=int(
                        _plan_override(plan, "seed_sequence_topk_per_seed", settings.defaults.seed_sequence_topk_per_seed)
                    ),
                    software_version=__version__,
                )
            elif stage_name == "seed_structure_recall":
                if seed_input is None:
                    raise RuntimeError("seed_structure_recall stage requires a seed input")
                structure_recall_result = run_seed_structure_recall_stage(
                    seed_faa=seed_input,
                    cluster_rep_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    colabfold_batch_bin=settings.tools.colabfold_batch_bin,
                    colabfold_data_dir=settings.tools.colabfold_data_dir,
                    foldseek_bin=settings.tools.foldseek_bin,
                    msa_mode=str(settings.defaults.colabfold_msa_mode),
                    num_models=int(settings.defaults.colabfold_num_models),
                    num_recycle=int(settings.defaults.colabfold_num_recycle),
                    min_tmscore=float(
                        _plan_override(plan, "seed_structure_min_tmscore", settings.defaults.seed_structure_min_tmscore)
                    ),
                    topk_per_seed=int(
                        _plan_override(plan, "seed_structure_topk_per_seed", settings.defaults.seed_structure_topk_per_seed)
                    ),
                    max_targets=int(
                        _plan_override(plan, "seed_structure_max_targets", settings.defaults.seed_structure_max_targets)
                    ),
                    software_version=__version__,
                )
            elif stage_name == "seed_recall_merge":
                merge_result = run_seed_recall_merge_stage(
                    cluster_rep_faa=current_input,
                    sequence_hits_tsv=sequence_result["sequence_hits_tsv"],
                    structure_hits_tsv=structure_recall_result["structure_hits_tsv"],
                    stage_dir=stage_dirs[stage_name],
                    software_version=__version__,
                )
                seeded_merge_rows = list(merge_result["seed_rows"])
                current_input = Path(merge_result["seeded_targets_faa"])
                skip_downstream_for_empty_seeded_run = not seeded_merge_rows
```

Short-circuit the thermo stages when needed:

```python
            elif stage_name == "temstapro_screen":
                if skip_downstream_for_empty_seeded_run:
                    continue
                thermo_result = run_temstapro_screen(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    conda_bin=settings.tools.conda_bin,
                    conda_env_name=settings.tools.temstapro_conda_env_name,
                    temstapro_bin=settings.tools.temstapro_bin,
                    repo_root=settings.tools.temstapro_repo_root,
                    model_dir=settings.tools.temstapro_model_dir,
                    cache_dir=settings.tools.temstapro_cache_dir,
                    hf_home=settings.tools.temstapro_hf_home,
                    transformers_offline=settings.tools.temstapro_transformers_offline,
                    top_fraction=float(_plan_override(plan, "thermo_top_fraction", settings.defaults.thermo_top_fraction)),
                    min_score=float(_plan_override(plan, "thermo_min_score", settings.defaults.thermo_min_score)),
                    software_version=__version__,
                )
                current_input = Path(thermo_result["thermo_hits_faa"])
            elif stage_name == "protrek_recall":
                if skip_downstream_for_empty_seeded_run:
                    continue
                protrek_result = run_protrek_stage(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    python_bin=settings.tools.protrek_python_bin,
                    index_script="scripts/protrek_build_index.py",
                    query_script="scripts/protrek_query.py",
                    repo_root=settings.tools.protrek_repo_root,
                    weights_dir=settings.tools.protrek_weights_dir,
                    query_texts=list(settings.defaults.protrek_query_texts),
                    batch_size=int(_plan_override(plan, "protrek_batch_size", settings.defaults.protrek_batch_size)),
                    top_k=int(_plan_override(plan, "protrek_top_k", settings.defaults.protrek_top_k)),
                    software_version=__version__,
                )
            elif stage_name == "structure_predict":
                if skip_downstream_for_empty_seeded_run:
                    continue
                structure_result = run_structure_predict_stage(
                    input_faa=current_input,
                    stage_dir=stage_dirs[stage_name],
                    colabfold_batch_bin=settings.tools.colabfold_batch_bin,
                    colabfold_data_dir=settings.tools.colabfold_data_dir,
                    msa_mode=str(settings.defaults.colabfold_msa_mode),
                    num_models=int(settings.defaults.colabfold_num_models),
                    num_recycle=int(settings.defaults.colabfold_num_recycle),
                    software_version=__version__,
                )
            elif stage_name == "foldseek_confirm":
                if skip_downstream_for_empty_seeded_run:
                    continue
                if structure_result is None:
                    raise RuntimeError("foldseek_confirm stage requires structure outputs")
                foldseek_result = run_foldseek_stage(
                    structure_manifest=list(structure_result["structure_manifest"]),
                    stage_dir=stage_dirs[stage_name],
                    foldseek_bin=settings.tools.foldseek_bin,
                    database_path=settings.tools.foldseek_database_path,
                    topk=int(_plan_override(plan, "foldseek_topk", settings.defaults.foldseek_topk)),
                    min_tmscore=float(_plan_override(plan, "foldseek_min_tmscore", settings.defaults.foldseek_min_tmscore)),
                    software_version=__version__,
                )
```

Update the `rerank_report` branch:

```python
            elif stage_name == "rerank_report":
                if skip_downstream_for_empty_seeded_run:
                    write_report_outputs(run_dir / "reports", run_dir.name, [])
                    continue
                if thermo_result is None or protrek_result is None or foldseek_result is None:
                    raise RuntimeError("rerank_report stage requires thermo, protrek, and foldseek outputs")
                hot_spring_ids = (
                    {record.protein_id for record in read_fasta(bundle["input_paths"][0])}
                    if bundle["bundle_type"] == "seeded_proteins"
                    else set()
                )
                combined_rows = combine_stage_scores(
                    thermo_rows=_read_scores_tsv(thermo_result["thermo_scores_tsv"]),
                    protrek_rows=_read_scores_tsv(protrek_result["protrek_scores_tsv"]),
                    foldseek_rows=_read_scores_tsv(foldseek_result["foldseek_scores_tsv"]),
                    hot_spring_ids=hot_spring_ids,
                    seed_rows=seeded_merge_rows,
                )
                write_report_outputs(run_dir / "reports", run_dir.name, combined_rows)
```

- [ ] **Step 4: Run the runner suite, then the full test suite**

Run:

```bash
pytest tests/control_plane/test_runner.py -v
pytest -q
```

Expected:

- the runner test file passes
- the full suite passes with the seeded runtime integrated

- [ ] **Step 5: Commit the seeded runner integration**

Run:

```bash
git add tests/control_plane/test_runner.py src/thermo_mining/control_plane/runner.py
git commit -m "feat(control-plane): run seeded protein jobs"
```

## Self-Review

### Spec coverage

- Seeded runtime contract, bundle type, defaults, and stage order: Task 1
- Planner awareness and bundle validation: Task 2
- Sequence recall stage: Task 3
- Structure recall stage and target cap: Task 4
- Merge union semantics and seed provenance reporting: Task 5
- CLI seeded entry point and empty-recall short-circuit: Task 6
- Control-plane `run-job` integration: Task 7

No spec requirement is left without a task.

### Placeholder scan

- No `TODO`
- No `TBD`
- No "implement later"
- No "similar to Task N"

Every task includes explicit file paths, concrete code, exact test commands, and a commit point.

### Type and naming consistency

The plan consistently uses:

- `seeded_proteins`
- `seed_paths`
- `run_seed_sequence_recall_stage`
- `run_seed_structure_recall_stage`
- `run_seed_recall_merge_stage`
- `run_seeded_pipeline`
- `seed_rows`

Those names match the approved spec and remain stable across all tasks.
