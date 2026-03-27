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

每个 stage 都遵循 `主输出 + scores.tsv + DONE.json` 的可恢复模式，便于断点续跑和审计。

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
