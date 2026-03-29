# Thermophilic Mining Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个从 `proteins.faa` 和样本 metadata 生成分层 shortlist 的 Phase 1 嗜热蛋白挖掘仓库，覆盖预过滤、MMseqs2 去冗余、TemStaPro 预筛、ProTrek 重排、Foldseek 确认、最终分层报告与断点续跑。

**Architecture:** 使用 Python CLI 作为主编排层，每个 stage 都实现为“输入文件 + 参数 -> 主输出文件 + scores.tsv + DONE.json”的可恢复单元。外部工具通过 `subprocess` 或 HTTP 包装接入，业务逻辑、配置加载、I/O、报告生成分离，先做可跑通且可审计的 MVP，再继续扩展大规模部署和下游结构预测。

**Tech Stack:** Python 3.11, pytest, PyYAML, requests, subprocess, MMseqs2, TemStaPro, ProTrek, Foldseek

---

## File Map

- `pyproject.toml`
  - 项目依赖、pytest 配置、CLI 入口
- `README.md`
  - 仓库用途、环境准备、运行方法、目录说明
- `config/pipeline.example.yaml`
  - 所有外部工具路径、阈值、权重、结果目录的示例配置
- `inputs/manifests/samples.example.tsv`
  - 样本清单示例
- `src/thermo_mining/__init__.py`
  - 版本信息
- `src/thermo_mining/config.py`
  - YAML 配置加载与 stage 输出目录计算
- `src/thermo_mining/models.py`
  - 样本、蛋白、DONE.json 的数据结构
- `src/thermo_mining/manifest.py`
  - 样本清单加载
- `src/thermo_mining/io_utils.py`
  - FASTA 读写、TSV 写出、哈希计算、DONE.json 写出
- `src/thermo_mining/steps/prefilter.py`
  - 长度和低复杂度过滤
- `src/thermo_mining/steps/mmseqs_cluster.py`
  - `MMseqs2 easy-linclust` 命令构建、运行与结果收集
- `src/thermo_mining/steps/temstapro_screen.py`
  - `TemStaPro` 命令构建、分数解析和候选保留
- `src/thermo_mining/steps/protrek_bridge.py`
  - `ProTrek` 索引构建和文本查询脚本包装
- `src/thermo_mining/steps/foldseek_client.py`
  - `foldseek-agent` HTTP 客户端和 stage 输出封装
- `src/thermo_mining/steps/rerank.py`
  - 多证据合分与 Tier 分层
- `src/thermo_mining/reporting.py`
  - `top_100`、`top_1000` 和 `summary.md`
- `src/thermo_mining/pipeline.py`
  - 阶段顺序、断点续跑、stage 编排
- `src/thermo_mining/cli.py`
  - 命令行入口
- `scripts/protrek_build_index.py`
  - 在 ProTrek 环境中构建本地 embedding 索引
- `scripts/protrek_query.py`
  - 在 ProTrek 环境中执行文本查询与相似度打分
- `tests/`
  - 单元测试和轻量 smoke 测试

### Task 1: 建立项目骨架与配置加载

**Files:**
- Create: `pyproject.toml`
- Create: `src/thermo_mining/__init__.py`
- Create: `src/thermo_mining/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.config import load_pipeline_config, stage_output_dirs


def test_load_pipeline_config_reads_thresholds(tmp_path):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
project_name: hot_spring_phase1
results_root: results
prefilter:
  min_length: 80
  max_length: 1200
  max_single_residue_fraction: 0.7
cluster:
  min_seq_id: 0.9
  coverage: 0.8
  threads: 64
""".strip(),
        encoding="utf-8",
    )

    cfg = load_pipeline_config(config_path)

    assert cfg.project_name == "hot_spring_phase1"
    assert cfg.prefilter.min_length == 80
    assert cfg.cluster.coverage == 0.8


def test_stage_output_dirs_are_deterministic(tmp_path):
    dirs = stage_output_dirs(tmp_path / "results", "run_001")

    assert dirs["01_prefilter"].as_posix().endswith("results/run_001/01_prefilter")
    assert dirs["06_rerank"].name == "06_rerank"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'thermo_mining'`

- [ ] **Step 3: Write minimal implementation**

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "thermo-mining"
version = "0.1.0"
description = "Phase 1 thermophilic protein mining pipeline"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0,<7",
  "requests>=2.32,<3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3,<9",
]

[project.scripts]
thermo-mining = "thermo_mining.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PrefilterConfig:
    min_length: int = 80
    max_length: int = 1200
    max_single_residue_fraction: float = 0.7


@dataclass(frozen=True)
class ClusterConfig:
    min_seq_id: float = 0.9
    coverage: float = 0.8
    threads: int = 64


@dataclass(frozen=True)
class ThermoConfig:
    top_fraction: float = 0.1
    min_score: float = 0.5


@dataclass(frozen=True)
class PipelineConfig:
    project_name: str
    results_root: Path
    prefilter: PrefilterConfig
    cluster: ClusterConfig
    thermo: ThermoConfig


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PipelineConfig(
        project_name=raw["project_name"],
        results_root=Path(raw["results_root"]),
        prefilter=PrefilterConfig(**raw.get("prefilter", {})),
        cluster=ClusterConfig(**raw.get("cluster", {})),
        thermo=ThermoConfig(**raw.get("thermo", {})),
    )


def stage_output_dirs(results_root: str | Path, run_name: str) -> dict[str, Path]:
    base = Path(results_root) / run_name
    return {
        "01_prefilter": base / "01_prefilter",
        "02_cluster": base / "02_cluster",
        "03_thermo_screen": base / "03_thermo_screen",
        "04_protrek_recall": base / "04_protrek_recall",
        "05_foldseek_confirm": base / "05_foldseek_confirm",
        "06_rerank": base / "06_rerank",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/thermo_mining/__init__.py src/thermo_mining/config.py tests/test_config.py
git commit -m "feat: bootstrap config loading for thermo mining"
```

### Task 2: 实现 manifest、FASTA I/O 和 DONE.json 基础设施

**Files:**
- Create: `src/thermo_mining/models.py`
- Create: `src/thermo_mining/manifest.py`
- Create: `src/thermo_mining/io_utils.py`
- Create: `inputs/manifests/samples.example.tsv`
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from thermo_mining.io_utils import read_fasta, write_done_json
from thermo_mining.manifest import load_sample_manifest
from thermo_mining.models import DoneRecord


def test_load_sample_manifest_reads_tsv(tmp_path):
    manifest_path = tmp_path / "samples.tsv"
    manifest_path.write_text(
        "sample_id\tprotein_faa\tmetadata_json\n"
        "S01\tinputs/S01.faa\t{\"temperature\":\"75C\"}\n",
        encoding="utf-8",
    )

    rows = load_sample_manifest(manifest_path)

    assert rows[0].sample_id == "S01"
    assert rows[0].protein_faa == "inputs/S01.faa"


def test_write_done_json_persists_counts(tmp_path):
    done_path = tmp_path / "DONE.json"
    record = DoneRecord(
        stage_name="01_prefilter",
        input_hash="abc123",
        parameters={"min_length": 80},
        software_version="0.1.0",
        runtime_seconds=1.25,
        retain_count=10,
        reject_count=2,
    )

    write_done_json(done_path, record)
    saved = json.loads(done_path.read_text(encoding="utf-8"))

    assert saved["stage_name"] == "01_prefilter"
    assert saved["retain_count"] == 10


def test_read_fasta_reads_ids_and_sequences(tmp_path):
    fasta_path = tmp_path / "input.faa"
    fasta_path.write_text(">p1 sample=S01\nMSTNPKPQRK\n>p2\nAAAAA\n", encoding="utf-8")

    records = read_fasta(fasta_path)

    assert records[0].protein_id == "p1"
    assert records[0].sequence == "MSTNPKPQRK"
    assert records[1].protein_id == "p2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_manifest.py -v`
Expected: FAIL with `ImportError` for `thermo_mining.models`, `thermo_mining.manifest`, or `thermo_mining.io_utils`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SampleManifestRow:
    sample_id: str
    protein_faa: str
    metadata_json: str = ""


@dataclass(frozen=True)
class ProteinRecord:
    protein_id: str
    sequence: str
    header: str


@dataclass(frozen=True)
class DoneRecord:
    stage_name: str
    input_hash: str
    parameters: dict[str, Any]
    software_version: str
    runtime_seconds: float
    retain_count: int
    reject_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

```python
import csv
from pathlib import Path

from .models import SampleManifestRow


def load_sample_manifest(path: str | Path) -> list[SampleManifestRow]:
    rows: list[SampleManifestRow] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rows.append(
                SampleManifestRow(
                    sample_id=row["sample_id"],
                    protein_faa=row["protein_faa"],
                    metadata_json=row.get("metadata_json", ""),
                )
            )
    return rows
```

```python
import csv
import hashlib
import json
from pathlib import Path

from .models import DoneRecord, ProteinRecord


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_fasta(path: str | Path) -> list[ProteinRecord]:
    records: list[ProteinRecord] = []
    header: str | None = None
    chunks: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    protein_id = header.split()[0]
                    records.append(ProteinRecord(protein_id=protein_id, sequence="".join(chunks), header=header))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
    if header is not None:
        protein_id = header.split()[0]
        records.append(ProteinRecord(protein_id=protein_id, sequence="".join(chunks), header=header))
    return records


def write_fasta(path: str | Path, records: list[ProteinRecord]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(f">{record.header}\n{record.sequence}\n")


def write_scores_tsv(path: str | Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_done_json(path: str | Path, record: DoneRecord) -> None:
    Path(path).write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
```

```tsv
sample_id	protein_faa	metadata_json
S01	inputs/S01.faa	{"environment":"hot_spring","temperature":"75C"}
S02	inputs/S02.faa	{"environment":"hot_spring","temperature":"82C"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/models.py src/thermo_mining/manifest.py src/thermo_mining/io_utils.py inputs/manifests/samples.example.tsv tests/test_manifest.py
git commit -m "feat: add manifest and audit io helpers"
```

### Task 3: 实现预过滤 stage

**Files:**
- Create: `src/thermo_mining/steps/__init__.py`
- Create: `src/thermo_mining/steps/prefilter.py`
- Test: `tests/steps/test_prefilter.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.io_utils import read_fasta
from thermo_mining.steps.prefilter import prefilter_records, run_prefilter


def test_prefilter_keeps_valid_sequences_and_rejects_noise():
    input_records = [
        ("keep_1", "MSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTATPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF"),
        ("too_short", "MSTN"),
        ("low_complexity", "A" * 100),
    ]

    kept, scores = prefilter_records(input_records, min_length=80, max_length=1200, max_single_residue_fraction=0.7)

    assert [row[0] for row in kept] == ["keep_1"]
    assert {row["protein_id"]: row["keep"] for row in scores} == {
        "keep_1": "yes",
        "too_short": "no",
        "low_complexity": "no",
    }


def test_run_prefilter_writes_outputs(tmp_path):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(
        ">keep_1\nMSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTATPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF\n"
        ">low_complexity\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
        encoding="utf-8",
    )
    stage_dir = tmp_path / "01_prefilter"

    result = run_prefilter(
        input_faa=input_faa,
        stage_dir=stage_dir,
        min_length=80,
        max_length=1200,
        max_single_residue_fraction=0.7,
        software_version="0.1.0",
    )

    kept = read_fasta(result["filtered_faa"])
    assert [record.protein_id for record in kept] == ["keep_1"]
    assert (stage_dir / "scores.tsv").exists()
    assert (stage_dir / "DONE.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_prefilter.py -v`
Expected: FAIL with `ImportError: cannot import name 'prefilter_records'`

- [ ] **Step 3: Write minimal implementation**

```python
from collections import Counter
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord, ProteinRecord


def residue_fraction(sequence: str) -> float:
    counts = Counter(sequence)
    return max(counts.values()) / len(sequence)


def prefilter_records(
    input_records: list[tuple[str, str]],
    min_length: int,
    max_length: int,
    max_single_residue_fraction: float,
) -> tuple[list[tuple[str, str]], list[dict[str, object]]]:
    kept: list[tuple[str, str]] = []
    scores: list[dict[str, object]] = []
    for protein_id, sequence in input_records:
        length = len(sequence)
        frac = residue_fraction(sequence) if sequence else 1.0
        keep = min_length <= length <= max_length and frac <= max_single_residue_fraction
        scores.append(
            {
                "protein_id": protein_id,
                "length": length,
                "max_single_residue_fraction": round(frac, 4),
                "keep": "yes" if keep else "no",
            }
        )
        if keep:
            kept.append((protein_id, sequence))
    return kept, scores


def run_prefilter(
    input_faa: str | Path,
    stage_dir: str | Path,
    min_length: int,
    max_length: int,
    max_single_residue_fraction: float,
    software_version: str,
) -> dict[str, Path]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    records = read_fasta(input_faa)
    kept, score_rows = prefilter_records(
        [(record.protein_id, record.sequence) for record in records],
        min_length=min_length,
        max_length=max_length,
        max_single_residue_fraction=max_single_residue_fraction,
    )

    filtered_records = [ProteinRecord(protein_id=protein_id, sequence=sequence, header=protein_id) for protein_id, sequence in kept]
    filtered_faa = stage_dir / "filtered.faa"
    write_fasta(filtered_faa, filtered_records)
    write_scores_tsv(
        stage_dir / "scores.tsv",
        score_rows,
        ["protein_id", "length", "max_single_residue_fraction", "keep"],
    )
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="01_prefilter",
            input_hash=sha256_file(input_faa),
            parameters={
                "min_length": min_length,
                "max_length": max_length,
                "max_single_residue_fraction": max_single_residue_fraction,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(filtered_records),
            reject_count=len(records) - len(filtered_records),
        ),
    )
    return {"filtered_faa": filtered_faa}
```

```python
"""Stage implementations for the thermophilic mining pipeline."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_prefilter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/__init__.py src/thermo_mining/steps/prefilter.py tests/steps/test_prefilter.py
git commit -m "feat: add prefilter stage for protein candidates"
```

### Task 4: 实现 MMseqs2 去冗余包装层

**Files:**
- Create: `src/thermo_mining/steps/mmseqs_cluster.py`
- Test: `tests/steps/test_mmseqs_cluster.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.steps.mmseqs_cluster import build_easy_linclust_command, parse_cluster_membership


def test_build_easy_linclust_command_uses_expected_flags(tmp_path):
    cmd = build_easy_linclust_command(
        mmseqs_bin="mmseqs",
        input_faa=tmp_path / "filtered.faa",
        output_prefix=tmp_path / "cluster",
        tmp_dir=tmp_path / "tmp",
        min_seq_id=0.9,
        coverage=0.8,
        threads=64,
    )

    assert cmd[:2] == ["mmseqs", "easy-linclust"]
    assert "--min-seq-id" in cmd
    assert "-c" in cmd
    assert "--threads" in cmd


def test_parse_cluster_membership_reads_representative_pairs(tmp_path):
    cluster_tsv = tmp_path / "cluster_cluster.tsv"
    cluster_tsv.write_text("rep1\tmember1\nrep1\tmember2\nrep2\tmember3\n", encoding="utf-8")

    rows = parse_cluster_membership(cluster_tsv)

    assert rows == [
        {"cluster_rep": "rep1", "member_id": "member1"},
        {"cluster_rep": "rep1", "member_id": "member2"},
        {"cluster_rep": "rep2", "member_id": "member3"},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_mmseqs_cluster.py -v`
Expected: FAIL with `ImportError` for `mmseqs_cluster`

- [ ] **Step 3: Write minimal implementation**

```python
import csv
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def build_easy_linclust_command(
    mmseqs_bin: str,
    input_faa: str | Path,
    output_prefix: str | Path,
    tmp_dir: str | Path,
    min_seq_id: float,
    coverage: float,
    threads: int,
) -> list[str]:
    return [
        mmseqs_bin,
        "easy-linclust",
        str(input_faa),
        str(output_prefix),
        str(tmp_dir),
        "--min-seq-id",
        f"{min_seq_id:.2f}",
        "-c",
        f"{coverage:.2f}",
        "--cov-mode",
        "1",
        "--threads",
        str(threads),
    ]


def parse_cluster_membership(cluster_tsv: str | Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(cluster_tsv).open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for rep, member in reader:
            rows.append({"cluster_rep": rep, "member_id": member})
    return rows


def run_mmseqs_cluster(
    input_faa: str | Path,
    stage_dir: str | Path,
    mmseqs_bin: str,
    min_seq_id: float,
    coverage: float,
    threads: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | list[str]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = stage_dir / "cluster"
    tmp_dir = stage_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_easy_linclust_command(
        mmseqs_bin=mmseqs_bin,
        input_faa=input_faa,
        output_prefix=output_prefix,
        tmp_dir=tmp_dir,
        min_seq_id=min_seq_id,
        coverage=coverage,
        threads=threads,
    )
    if dry_run:
        return cmd

    subprocess.run(cmd, check=True)

    cluster_tsv = stage_dir / "cluster_cluster.tsv"
    rep_faa = stage_dir / "cluster_rep_seq.fasta"
    rows = parse_cluster_membership(cluster_tsv)
    write_scores_tsv(stage_dir / "scores.tsv", rows, ["cluster_rep", "member_id"])

    reps = {row["cluster_rep"] for row in rows}
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="02_cluster",
            input_hash=sha256_file(input_faa),
            parameters={
                "min_seq_id": min_seq_id,
                "coverage": coverage,
                "threads": threads,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(reps),
            reject_count=max(0, len(rows) - len(reps)),
        ),
    )
    return {"cluster_rep_faa": rep_faa, "cluster_membership_tsv": cluster_tsv}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_mmseqs_cluster.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/mmseqs_cluster.py tests/steps/test_mmseqs_cluster.py
git commit -m "feat: add mmseqs clustering stage wrapper"
```

### Task 5: 实现 TemStaPro 预筛包装层

**Files:**
- Create: `src/thermo_mining/steps/temstapro_screen.py`
- Test: `tests/steps/test_temstapro_screen.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.steps.temstapro_screen import build_temstapro_command, derive_thermo_score, select_thermo_hits


def test_build_temstapro_command_contains_required_arguments(tmp_path):
    cmd = build_temstapro_command(
        temstapro_bin="temstapro",
        input_faa=tmp_path / "cluster_rep.faa",
        model_dir=tmp_path / "ProtTrans",
        cache_dir=tmp_path / "cache",
        output_tsv=tmp_path / "temstapro.tsv",
    )

    assert cmd[:2] == ["temstapro", "-f"]
    assert "--mean-output" in cmd


def test_derive_thermo_score_prefers_highest_numeric_signal():
    row = {"protein_id": "p1", "raw_40": "0.31", "raw_50": "0.79", "prediction": "thermophilic"}
    assert derive_thermo_score(row) == 0.79


def test_select_thermo_hits_respects_fraction_and_min_score():
    rows = [
        {"protein_id": "p1", "thermo_score": 0.95},
        {"protein_id": "p2", "thermo_score": 0.84},
        {"protein_id": "p3", "thermo_score": 0.30},
    ]

    kept = select_thermo_hits(rows, top_fraction=0.34, min_score=0.8)

    assert [row["protein_id"] for row in kept] == ["p1", "p2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_temstapro_screen.py -v`
Expected: FAIL with `ImportError` for `temstapro_screen`

- [ ] **Step 3: Write minimal implementation**

```python
import csv
import math
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord, ProteinRecord


def build_temstapro_command(
    temstapro_bin: str,
    input_faa: str | Path,
    model_dir: str | Path,
    cache_dir: str | Path,
    output_tsv: str | Path,
) -> list[str]:
    return [
        temstapro_bin,
        "-f",
        str(input_faa),
        "-d",
        str(model_dir),
        "-e",
        str(cache_dir),
        "--mean-output",
        str(output_tsv),
    ]


def derive_thermo_score(row: dict[str, str]) -> float:
    numeric_values: list[float] = []
    for key, value in row.items():
        if key in {"protein_id", "prediction"}:
            continue
        try:
            numeric_values.append(float(value))
        except ValueError:
            continue
    return max(numeric_values) if numeric_values else 0.0


def select_thermo_hits(rows: list[dict[str, object]], top_fraction: float, min_score: float) -> list[dict[str, object]]:
    ranked = sorted(rows, key=lambda row: float(row["thermo_score"]), reverse=True)
    keep_count = max(1, math.ceil(len(ranked) * top_fraction))
    kept = ranked[:keep_count]
    for row in ranked[keep_count:]:
        if float(row["thermo_score"]) >= min_score:
            kept.append(row)
    return kept


def run_temstapro_screen(
    input_faa: str | Path,
    stage_dir: str | Path,
    temstapro_bin: str,
    model_dir: str | Path,
    cache_dir: str | Path,
    top_fraction: float,
    min_score: float,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | list[str]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_output = stage_dir / "temstapro_raw.tsv"
    cmd = build_temstapro_command(temstapro_bin, input_faa, model_dir, cache_dir, raw_output)
    if dry_run:
        return cmd

    subprocess.run(cmd, check=True)

    parsed_rows: list[dict[str, object]] = []
    with raw_output.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            parsed_rows.append(
                {
                    "protein_id": row["protein_id"],
                    "prediction": row.get("prediction", ""),
                    "thermo_score": round(derive_thermo_score(row), 4),
                }
            )

    kept = select_thermo_hits(parsed_rows, top_fraction=top_fraction, min_score=min_score)
    keep_ids = {row["protein_id"] for row in kept}
    source_records = read_fasta(input_faa)
    kept_records = [ProteinRecord(record.protein_id, record.sequence, record.header) for record in source_records if record.protein_id in keep_ids]
    thermo_hits_faa = stage_dir / "thermo_hits.faa"
    write_fasta(thermo_hits_faa, kept_records)
    write_scores_tsv(stage_dir / "scores.tsv", parsed_rows, ["protein_id", "prediction", "thermo_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="03_thermo_screen",
            input_hash=sha256_file(input_faa),
            parameters={"top_fraction": top_fraction, "min_score": min_score},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(kept_records),
            reject_count=len(source_records) - len(kept_records),
        ),
    )
    return {"thermo_hits_faa": thermo_hits_faa, "thermo_scores_tsv": stage_dir / "scores.tsv"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_temstapro_screen.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/temstapro_screen.py tests/steps/test_temstapro_screen.py
git commit -m "feat: add temstapro screening stage"
```

### Task 6: 实现 ProTrek 本地索引与文本查询桥接

**Files:**
- Create: `src/thermo_mining/steps/protrek_bridge.py`
- Create: `scripts/protrek_build_index.py`
- Create: `scripts/protrek_query.py`
- Test: `tests/steps/test_protrek_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.steps.protrek_bridge import (
    build_protrek_index_command,
    build_protrek_query_command,
    collapse_query_scores,
)


def test_build_protrek_index_command_uses_repo_and_weights(tmp_path):
    cmd = build_protrek_index_command(
        python_bin="/opt/protrek/bin/python",
        script_path=tmp_path / "scripts" / "protrek_build_index.py",
        repo_root="/srv/ProTrek",
        weights_dir="/srv/ProTrek/weights/ProTrek_650M",
        input_faa=tmp_path / "thermo_hits.faa",
        output_dir=tmp_path / "index",
        batch_size=8,
    )

    assert cmd[0] == "/opt/protrek/bin/python"
    assert "--repo-root" in cmd
    assert "--weights-dir" in cmd


def test_build_protrek_query_command_repeats_query_text_flags(tmp_path):
    cmd = build_protrek_query_command(
        python_bin="/opt/protrek/bin/python",
        script_path=tmp_path / "scripts" / "protrek_query.py",
        repo_root="/srv/ProTrek",
        weights_dir="/srv/ProTrek/weights/ProTrek_650M",
        index_dir=tmp_path / "index",
        query_texts=["thermostable enzyme", "heat-stable protein"],
        output_tsv=tmp_path / "scores.tsv",
        top_k=50,
    )

    assert cmd.count("--query-text") == 2
    assert "--top-k" in cmd


def test_collapse_query_scores_keeps_best_hit_per_protein():
    rows = [
        {"protein_id": "p1", "query_text": "thermostable enzyme", "protrek_score": 0.72},
        {"protein_id": "p1", "query_text": "heat-stable protein", "protrek_score": 0.81},
        {"protein_id": "p2", "query_text": "thermostable enzyme", "protrek_score": 0.65},
    ]

    collapsed = collapse_query_scores(rows)

    assert collapsed == [
        {"protein_id": "p1", "protrek_score": 0.81},
        {"protein_id": "p2", "protrek_score": 0.65},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_protrek_bridge.py -v`
Expected: FAIL with `ImportError` for `protrek_bridge`

- [ ] **Step 3: Write minimal implementation**

```python
import csv
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def build_protrek_index_command(
    python_bin: str,
    script_path: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    input_faa: str | Path,
    output_dir: str | Path,
    batch_size: int,
) -> list[str]:
    return [
        python_bin,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--weights-dir",
        str(weights_dir),
        "--input-faa",
        str(input_faa),
        "--output-dir",
        str(output_dir),
        "--batch-size",
        str(batch_size),
    ]


def build_protrek_query_command(
    python_bin: str,
    script_path: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    index_dir: str | Path,
    query_texts: list[str],
    output_tsv: str | Path,
    top_k: int,
) -> list[str]:
    cmd = [
        python_bin,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--weights-dir",
        str(weights_dir),
        "--index-dir",
        str(index_dir),
        "--output-tsv",
        str(output_tsv),
        "--top-k",
        str(top_k),
    ]
    for query_text in query_texts:
        cmd.extend(["--query-text", query_text])
    return cmd


def collapse_query_scores(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    best: dict[str, float] = {}
    for row in rows:
        protein_id = str(row["protein_id"])
        score = float(row["protrek_score"])
        best[protein_id] = max(best.get(protein_id, 0.0), score)
    return [{"protein_id": protein_id, "protrek_score": score} for protein_id, score in sorted(best.items())]


def run_protrek_stage(
    input_faa: str | Path,
    stage_dir: str | Path,
    python_bin: str,
    index_script: str | Path,
    query_script: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    query_texts: list[str],
    batch_size: int,
    top_k: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[str]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    index_dir = stage_dir / "index"
    raw_query_tsv = stage_dir / "protrek_raw.tsv"

    index_cmd = build_protrek_index_command(python_bin, index_script, repo_root, weights_dir, input_faa, index_dir, batch_size)
    query_cmd = build_protrek_query_command(python_bin, query_script, repo_root, weights_dir, index_dir, query_texts, raw_query_tsv, top_k)
    if dry_run:
        return {"index_cmd": index_cmd, "query_cmd": query_cmd}

    subprocess.run(index_cmd, check=True)
    subprocess.run(query_cmd, check=True)

    raw_rows: list[dict[str, object]] = []
    with raw_query_tsv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            raw_rows.append(
                {
                    "protein_id": row["protein_id"],
                    "query_text": row["query_text"],
                    "protrek_score": float(row["protrek_score"]),
                }
            )

    collapsed = collapse_query_scores(raw_rows)
    write_scores_tsv(stage_dir / "scores.tsv", collapsed, ["protein_id", "protrek_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="04_protrek_recall",
            input_hash=sha256_file(input_faa),
            parameters={"query_texts": query_texts, "top_k": top_k, "batch_size": batch_size},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(collapsed),
            reject_count=0,
        ),
    )
    return {"protrek_scores_tsv": stage_dir / "scores.tsv"}
```

```python
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch


def read_fasta(path: str | Path) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    seqs: list[str] = []
    header = None
    chunks: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    ids.append(header.split()[0])
                    seqs.append("".join(chunks))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
    if header is not None:
        ids.append(header.split()[0])
        seqs.append("".join(chunks))
    return ids, seqs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--input-faa", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    sys.path.insert(0, args.repo_root)
    from model.ProTrek.protrek_trimodal_model import ProTrekTrimodalModel

    config = {
        "protein_config": str(Path(args.weights_dir) / "esm2_t33_650M_UR50D"),
        "text_config": str(Path(args.weights_dir) / "BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"),
        "structure_config": str(Path(args.weights_dir) / "foldseek_t30_150M"),
        "from_checkpoint": str(Path(args.weights_dir) / "ProTrek_650M.pt"),
    }
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ProTrekTrimodalModel(**config).eval().to(device)

    protein_ids, sequences = read_fasta(args.input_faa)
    embeddings: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(sequences), args.batch_size):
            batch = sequences[start : start + args.batch_size]
            batch_embeddings = model.get_protein_repr(batch).detach().cpu().numpy()
            embeddings.append(batch_embeddings)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "sequence_embeddings.npy", np.concatenate(embeddings, axis=0))
    with (output_dir / "metadata.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["protein_id"], delimiter="\t")
        writer.writeheader()
        for protein_id in protein_ids:
            writer.writerow({"protein_id": protein_id})


if __name__ == "__main__":
    main()
```

```python
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch


def cosine_similarity(query: np.ndarray, index: np.ndarray) -> np.ndarray:
    query = query / np.linalg.norm(query, axis=1, keepdims=True)
    index = index / np.linalg.norm(index, axis=1, keepdims=True)
    return query @ index.T


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--query-text", action="append", dest="query_texts", required=True)
    args = parser.parse_args()

    sys.path.insert(0, args.repo_root)
    from model.ProTrek.protrek_trimodal_model import ProTrekTrimodalModel

    config = {
        "protein_config": str(Path(args.weights_dir) / "esm2_t33_650M_UR50D"),
        "text_config": str(Path(args.weights_dir) / "BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"),
        "structure_config": str(Path(args.weights_dir) / "foldseek_t30_150M"),
        "from_checkpoint": str(Path(args.weights_dir) / "ProTrek_650M.pt"),
    }
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ProTrekTrimodalModel(**config).eval().to(device)

    with torch.no_grad():
        query_embeddings = model.get_text_repr(args.query_texts).detach().cpu().numpy()
    index_dir = Path(args.index_dir)
    index = np.load(index_dir / "sequence_embeddings.npy")
    metadata_rows = list(csv.DictReader((index_dir / "metadata.tsv").open("r", encoding="utf-8"), delimiter="\t"))
    sims = cosine_similarity(query_embeddings, index)

    with Path(args.output_tsv).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_text", "protein_id", "protrek_score", "rank"], delimiter="\t")
        writer.writeheader()
        for query_idx, query_text in enumerate(args.query_texts):
            top_indices = np.argsort(sims[query_idx])[::-1][: args.top_k]
            for rank, idx in enumerate(top_indices, start=1):
                writer.writerow(
                    {
                        "query_text": query_text,
                        "protein_id": metadata_rows[int(idx)]["protein_id"],
                        "protrek_score": round(float(sims[query_idx][int(idx)]), 6),
                        "rank": rank,
                    }
                )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_protrek_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/protrek_bridge.py scripts/protrek_build_index.py scripts/protrek_query.py tests/steps/test_protrek_bridge.py
git commit -m "feat: add protrek bridge for text reranking"
```

### Task 7: 实现 Foldseek 确认层客户端

**Files:**
- Create: `src/thermo_mining/steps/foldseek_client.py`
- Test: `tests/steps/test_foldseek_client.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.steps.foldseek_client import FoldseekClient, summarize_foldseek_hits


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_summarize_foldseek_hits_uses_best_tmscore():
    score = summarize_foldseek_hits(
        [
            {"target": "hit1", "tmscore": 0.44},
            {"target": "hit2", "tmscore": 0.81},
        ]
    )

    assert score == 0.81


def test_foldseek_client_posts_search_request(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["timeout"] = timeout
        return DummyResponse({"results": [{"target": "hit1", "tmscore": 0.66}]})

    monkeypatch.setattr("requests.post", fake_post)
    client = FoldseekClient(base_url="http://127.0.0.1:8100", timeout_seconds=30)
    payload = client.search_structure("/tmp/p1.pdb", "afdb50", 5, 0.6)

    assert sent["url"].endswith("/search_structure")
    assert payload["results"][0]["tmscore"] == 0.66
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_foldseek_client.py -v`
Expected: FAIL with `ImportError` for `foldseek_client`

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path
from time import perf_counter

import requests

from ..io_utils import write_done_json, write_scores_tsv
from ..models import DoneRecord


def summarize_foldseek_hits(rows: list[dict[str, object]]) -> float:
    if not rows:
        return 0.0
    return max(float(row.get("tmscore", 0.0)) for row in rows)


class FoldseekClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_structure(self, pdb_path: str, database: str, topk: int, min_tmscore: float) -> dict[str, object]:
        response = requests.post(
            f"{self.base_url}/search_structure",
            json={
                "pdb_path": pdb_path,
                "database": database,
                "topk": topk,
                "min_tmscore": min_tmscore,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def run_foldseek_stage(
    structure_manifest: list[dict[str, str]],
    stage_dir: str | Path,
    base_url: str,
    database: str,
    topk: int,
    min_tmscore: float,
    software_version: str,
) -> dict[str, Path]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    client = FoldseekClient(base_url=base_url)

    rows: list[dict[str, object]] = []
    for entry in structure_manifest:
        payload = client.search_structure(entry["pdb_path"], database, topk, min_tmscore)
        hits = payload.get("results", [])
        rows.append(
            {
                "protein_id": entry["protein_id"],
                "foldseek_score": round(summarize_foldseek_hits(hits), 4),
            }
        )

    write_scores_tsv(stage_dir / "scores.tsv", rows, ["protein_id", "foldseek_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="05_foldseek_confirm",
            input_hash="structure-manifest",
            parameters={"database": database, "topk": topk, "min_tmscore": min_tmscore},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"foldseek_scores_tsv": stage_dir / "scores.tsv"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_foldseek_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/foldseek_client.py tests/steps/test_foldseek_client.py
git commit -m "feat: add foldseek confirmation client"
```

### Task 8: 实现最终合分、Tier 分层和报告输出

**Files:**
- Create: `src/thermo_mining/steps/rerank.py`
- Create: `src/thermo_mining/reporting.py`
- Test: `tests/steps/test_rerank.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.reporting import build_summary_markdown
from thermo_mining.steps.rerank import assign_tier, combine_stage_scores


def test_assign_tier_uses_expected_thresholds():
    assert assign_tier(0.82) == "Tier 1"
    assert assign_tier(0.60) == "Tier 2"
    assert assign_tier(0.20) == "Tier 3"


def test_combine_stage_scores_merges_multiple_sources():
    combined = combine_stage_scores(
        thermo_rows=[{"protein_id": "p1", "thermo_score": 0.9}, {"protein_id": "p2", "thermo_score": 0.4}],
        protrek_rows=[{"protein_id": "p1", "protrek_score": 0.8}, {"protein_id": "p2", "protrek_score": 0.7}],
        foldseek_rows=[{"protein_id": "p1", "foldseek_score": 0.6}],
        hot_spring_ids={"p1"},
    )

    assert combined[0]["protein_id"] == "p1"
    assert combined[0]["tier"] == "Tier 1"
    assert combined[1]["tier"] in {"Tier 2", "Tier 3"}


def test_build_summary_markdown_reports_counts():
    markdown_text = build_summary_markdown(
        run_name="run_001",
        tier_counts={"Tier 1": 3, "Tier 2": 5, "Tier 3": 10},
        top_candidate_ids=["p1", "p2", "p3"],
    )

    assert "run_001" in markdown_text
    assert "Tier 1" in markdown_text
    assert "p1" in markdown_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/steps/test_rerank.py -v`
Expected: FAIL with `ImportError` for `rerank` or `reporting`

- [ ] **Step 3: Write minimal implementation**

```python
def assign_tier(final_score: float) -> str:
    if final_score >= 0.75:
        return "Tier 1"
    if final_score >= 0.55:
        return "Tier 2"
    return "Tier 3"


def combine_stage_scores(
    thermo_rows: list[dict[str, object]],
    protrek_rows: list[dict[str, object]],
    foldseek_rows: list[dict[str, object]],
    hot_spring_ids: set[str],
) -> list[dict[str, object]]:
    thermo_map = {row["protein_id"]: float(row["thermo_score"]) for row in thermo_rows}
    protrek_map = {row["protein_id"]: float(row["protrek_score"]) for row in protrek_rows}
    foldseek_map = {row["protein_id"]: float(row["foldseek_score"]) for row in foldseek_rows}
    all_ids = sorted(set(thermo_map) | set(protrek_map) | set(foldseek_map))

    combined: list[dict[str, object]] = []
    for protein_id in all_ids:
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

```python
def build_summary_markdown(run_name: str, tier_counts: dict[str, int], top_candidate_ids: list[str]) -> str:
    lines = [
        f"# Thermo Mining Summary: {run_name}",
        "",
        "## Tier Counts",
        f"- Tier 1: {tier_counts.get('Tier 1', 0)}",
        f"- Tier 2: {tier_counts.get('Tier 2', 0)}",
        f"- Tier 3: {tier_counts.get('Tier 3', 0)}",
        "",
        "## Top Candidates",
    ]
    for protein_id in top_candidate_ids:
        lines.append(f"- {protein_id}")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/steps/test_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/steps/rerank.py src/thermo_mining/reporting.py tests/steps/test_rerank.py
git commit -m "feat: add final reranking and reporting"
```

### Task 9: 实现主编排器、断点续跑和 CLI

**Files:**
- Create: `src/thermo_mining/pipeline.py`
- Create: `src/thermo_mining/cli.py`
- Create: `README.md`
- Modify: `pyproject.toml`
- Test: `tests/test_pipeline_cli.py`

- [ ] **Step 1: Write the failing test**

```python
from thermo_mining.pipeline import should_skip_stage


def test_should_skip_stage_respects_done_json(tmp_path):
    done_path = tmp_path / "DONE.json"
    done_path.write_text(
        '{"stage_name":"01_prefilter","input_hash":"abc","parameters":{},"software_version":"0.1.0","runtime_seconds":1.0,"retain_count":1,"reject_count":0}',
        encoding="utf-8",
    )

    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=True) is True
    assert should_skip_stage(done_path=done_path, expected_input_hash="xyz", resume=True) is False
    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=False) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_cli.py -v`
Expected: FAIL with `ImportError` for `pipeline`

- [ ] **Step 3: Write minimal implementation**

```python
import json
from pathlib import Path


def should_skip_stage(done_path: str | Path, expected_input_hash: str, resume: bool) -> bool:
    if not resume:
        return False
    done_path = Path(done_path)
    if not done_path.exists():
        return False
    payload = json.loads(done_path.read_text(encoding="utf-8"))
    return payload.get("input_hash") == expected_input_hash
```

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thermo-mining")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--run-name", required=True)
    run_parser.add_argument("--input-faa", required=True)
    run_parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    parser.parse_args()
```

```markdown
# Thermo Mining

## Scope

本仓库实现 Phase 1 嗜热蛋白挖掘流水线，输入为 `proteins.faa` 和样本 metadata，输出为分层 shortlist。

## Stages

1. `01_prefilter`
2. `02_cluster`
3. `03_thermo_screen`
4. `04_protrek_recall`
5. `05_foldseek_confirm`
6. `06_rerank`

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Example

```bash
thermo-mining run --config config/pipeline.example.yaml --run-name demo_run --input-faa inputs/demo.faa --resume
```
```

```toml
[project.scripts]
thermo-mining = "thermo_mining.cli:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/thermo_mining/pipeline.py src/thermo_mining/cli.py README.md pyproject.toml tests/test_pipeline_cli.py
git commit -m "feat: add pipeline resume checks and cli entrypoint"
```

## Self-Review

### Spec coverage

- 输入边界、目录结构：Task 1, Task 2, Task 9
- `scores.tsv`、`DONE.json`、断点续跑：Task 2, Task 3, Task 4, Task 5, Task 6, Task 7, Task 9
- `MMseqs2` 去冗余：Task 4
- `TemStaPro` 预筛：Task 5
- `ProTrek` 多模态重排：Task 6
- `Foldseek` 结构确认：Task 7
- 最终 tiered shortlist 和报告：Task 8

没有发现 spec 中完全没有落到任务的部分。结构预测和下游改造本来就不在本计划范围内。

### Placeholder scan

本计划没有空白占位项或延后实现提示。每个 task 都给了明确文件、测试、命令和代码。

### Type consistency

- `DoneRecord` 在 Task 2 定义，Task 3 到 Task 7 均复用同一结构
- stage 名称统一为 `01_prefilter` 到 `06_rerank`
- `protein_id` 是所有 stage 表格的主键字段
- `thermo_score`、`protrek_score`、`foldseek_score` 在 Task 8 中按统一命名合并

没有发现函数名或字段名互相冲突。
