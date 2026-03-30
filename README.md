# Thermo Mining

Phase 1 implements a thermophilic protein mining pipeline plus a thin single-user control plane.

## Stages

1. `01_prefilter`
2. `02_cluster`
3. `03_thermo_screen`
4. `04_protrek_recall`
5. `05_foldseek_confirm`
6. `06_rerank`

Each stage writes resumable artifacts such as primary outputs, `scores.tsv`, and `DONE.json`.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## CLI

```bash
thermo-mining run ...
thermo-mining serve --config config/platform.example.yaml
thermo-mining run-job --run-dir runs/<run_id>
```

## Control Plane MVP

- Single-user FastAPI console
- Server-side path browsing
- Plan review and confirm flow
- One active tmux-backed run at a time
- Artifacts and runtime status from `runtime_state.json`

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
