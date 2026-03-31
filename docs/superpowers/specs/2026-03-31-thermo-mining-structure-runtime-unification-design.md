# Thermo Mining Structure Runtime Unification Design

## Goal

Finish the remaining server-runtime gap between ProTrek recall and Foldseek
confirmation by adding an explicit structure-prediction stage backed by
LocalColabFold, replacing Foldseek HTTP mode with direct local binary
execution, and unifying both the control-plane and CLI entry points onto the
same platform-config-driven runtime contract.

After this change, the repo should be able to run the structure side of the
pipeline on the target Ubuntu host without assuming pre-existing PDB files,
without requiring a Foldseek HTTP service, and without maintaining a separate
legacy CLI configuration model.

## Context

Current repo state:

- TemStaPro runtime configuration support is already being implemented in the
  working tree, but not yet committed.
- `foldseek_confirm` currently assumes `structures/<protein_id>.pdb` already
  exists and only sends those paths to an HTTP service.
- No tracked code currently calls `localcolabfold` / `colabfold_batch`.
- The control plane uses `settings.py` and platform YAML, while the legacy CLI
  path still uses `config.py` and a separate `PipelineConfig` shape.
- The target server has LocalColabFold available and the AlphaFold parameter
  cache can live outside the repo under a server-local cache root.

That leaves one functional hole and one structural hole:

1. There is no stage that actually generates structures for Foldseek input.
2. The repo still has two runtime-configuration contracts for two entry points.

## In Scope

- Add an explicit structure-prediction stage between ProTrek and Foldseek
- Run LocalColabFold through configured binary and data-root paths
- Normalize LocalColabFold outputs into deterministic `structures/*.pdb`
- Replace Foldseek HTTP-client execution with local Foldseek binary execution
- Add Foldseek binary and LocalColabFold runtime fields to platform settings
- Unify the CLI `run` path and the control-plane `run-job` path onto platform
  settings
- Update tests, config examples, and docs to reflect the new stage layout and
  runtime contract

## Out of Scope

- Downloading AlphaFold/ColabFold model parameters inside the repo
- Tracking model caches in git
- GPU tuning, performance optimization, or parallel scheduling for ColabFold
- Reworking ProTrek ranking behavior
- Solving remote job distribution or multi-user execution

## Locked Decisions

- Add a dedicated stage named `structure_predict`; do not hide structure
  generation inside `foldseek_confirm`.
- Use LocalColabFold by invoking a configured `colabfold_batch` executable
  directly; do not require shell activation.
- Use configured cache/data roots for ColabFold model assets; do not place
  model parameters under the repo tree.
- Run Foldseek through the local binary with a configured on-disk database path;
  do not keep HTTP mode as the primary runtime path.
- Unify CLI and control-plane execution on platform config from
  `src/thermo_mining/settings.py`.
- Treat old numbered stage directories as incompatible with the new stage graph;
  existing historical runs are not guaranteed to resume after this migration.

## Architecture

### Unified Runtime Contract

`PlatformSettings` becomes the single runtime configuration model for both:

- `thermo-mining run`
- `thermo-mining run-job`

The legacy `PipelineConfig` path is removed from active execution. The CLI
still accepts `--config`, but that file is now the same platform YAML used by
the control plane.

This keeps the runtime contract in one place:

- tool binaries and deployment paths under `tools`
- output roots under `runtime`
- thresholds and tuning defaults under `defaults`

### Stage Graph Change

Insert a new stage:

- `structure_predict`

New high-level order for protein-only runs:

- `prefilter`
- `mmseqs_cluster`
- `temstapro_screen`
- `protrek_recall`
- `structure_predict`
- `foldseek_confirm`
- `rerank_report`

For contig and paired-fastq runs, `structure_predict` is inserted in the same
position relative to `protrek_recall` and `foldseek_confirm`.

### Stage Directory Numbering

The new numbered stage layout for protein-only runs becomes:

- `01_prefilter`
- `02_cluster`
- `03_temstapro`
- `04_protrek`
- `05_structure`
- `06_foldseek`
- `07_report`

Equivalent later-stage numbering shifts apply to other bundle types. This is a
breaking layout change for resume compatibility with prior run directories.

## Configuration Additions

Add these `tools` fields to `PlatformSettings` and platform YAML:

- `colabfold_batch_bin`
  - Full executable path for `colabfold_batch`
  - Example:
    - `/mnt/disk3/tio_nekton4/localcolabfold/.pixi/envs/default/bin/colabfold_batch`
- `colabfold_data_dir`
  - Data root passed to `--data`
  - Example:
    - `/mnt/disk3/tio_nekton4/.cache/colabfold`
- `foldseek_bin`
  - Full executable path for `foldseek`
  - Example:
    - `/mnt/disk3/tio_nekton4/foldseek/bin/foldseek`
- `foldseek_database_path`
  - On-disk Foldseek target database path
  - Example:
    - `/mnt/disk3/tio_nekton4/foldseek/db/afdb50`

Add these `defaults` fields:

- `colabfold_msa_mode`
  - Default: `single_sequence`
- `colabfold_num_models`
  - Default: `1`
- `colabfold_num_recycle`
  - Default: `1`

Keep these existing Foldseek defaults:

- `foldseek_topk`
- `foldseek_min_tmscore`

`foldseek_database` under `defaults` is removed from the active runtime path
because local binary mode needs an actual database path, not a service-level
logical name.

## LocalColabFold Runtime Behavior

### Command Shape

Each protein is predicted with an isolated invocation shaped like:

```bash
<colabfold_batch_bin> \
  --data <colabfold_data_dir> \
  --msa-mode <colabfold_msa_mode> \
  --num-models <colabfold_num_models> \
  --num-recycle <colabfold_num_recycle> \
  <query_fasta> \
  <raw_output_dir>
```

### Per-Protein Execution Model

Run LocalColabFold once per protein rather than submitting a single
multi-sequence batch.

Rationale:

- deterministic mapping from `protein_id` to one isolated output directory
- simpler recovery and debugging when one sequence fails
- avoids coupling repo behavior to version-specific ColabFold batch filename
  conventions for multi-query output parsing

### Stage Outputs

`structure_predict` writes:

- `queries/<protein_id>.faa`
- `raw/<protein_id>/...` LocalColabFold raw output
- `structures/<protein_id>.pdb`
- `structure_manifest.json`
- `DONE.json`

`structure_manifest.json` is the contract to the Foldseek stage and contains,
for each retained protein:

- `protein_id`
- `pdb_path`

### PDB Normalization Rule

The stage must copy exactly one chosen PDB per protein into:

- `structures/<protein_id>.pdb`

The normalization rule is:

1. prefer the first ranked PDB emitted for that protein
2. fail the stage if no PDB is produced
3. fail the stage if multiple candidate PDBs are present but no deterministic
   first-ranked file can be identified

This keeps the downstream Foldseek stage independent from ColabFold's internal
output directory naming.

## Foldseek Binary Runtime Behavior

### Command Shape

For each normalized PDB, execute Foldseek locally with a command shaped like:

```bash
<foldseek_bin> easy-search \
  <query_pdb> \
  <foldseek_database_path> \
  <result_tsv> \
  <tmp_dir> \
  --format-output query,target,alntmscore \
  --max-seqs <foldseek_topk>
```

### Score Derivation

Parse the TSV output and:

- discard hits whose `alntmscore` is below `foldseek_min_tmscore`
- compute `foldseek_score` as the maximum remaining `alntmscore`
- emit `0.0` when no hit survives filtering

This preserves the current stage contract of one summarized foldseek score per
protein without relying on an external HTTP adapter.

### Stage Inputs And Outputs

`foldseek_confirm` now consumes `structure_manifest.json` instead of inventing a
manifest from the FASTA input.

It writes:

- per-query raw Foldseek result TSV files under the stage directory
- summarized `scores.tsv`
- `DONE.json`

## CLI And Control Plane Unification

### Shared Execution Model

The repo keeps both entry points, but they should execute the same runtime
behavior:

- `run-job` continues to execute a reviewed plan under the control plane
- `run` remains a direct CLI entry point for a protein FASTA input

Both paths must load platform config through `load_settings()` and pass the
same tool/default values into the same stage functions.

### CLI Output Root

For `thermo-mining run`, output directories now derive from:

- `settings.runtime.runs_root`
- `--run-name`

That replaces the old standalone `results_root` field from `PipelineConfig`.

### Legacy Config Migration

The active runtime must no longer depend on:

- `src/thermo_mining/config.py`
- `PipelineConfig`
- `foldseek.base_url`
- old thermo-only config sections that bypass platform settings

It is acceptable to keep compatibility shims temporarily if tests or imports
need them, but runtime execution must no longer branch on a second config
schema.

## File-Level Design Impact

### `src/thermo_mining/settings.py`

- extend `ToolSettings` with LocalColabFold and Foldseek binary fields
- extend `DefaultSettings` with ColabFold tuning defaults
- remove active reliance on `foldseek_database` as a logical service name

### `src/thermo_mining/control_plane/stage_graph.py`

- insert `structure_predict` in every applicable stage order

### `src/thermo_mining/control_plane/runner.py`

- call the new structure-prediction stage after ProTrek
- feed `structure_manifest.json` or equivalent returned manifest into Foldseek
- use configured local Foldseek binary and database path

### `src/thermo_mining/pipeline.py`

- migrate CLI runtime path to the same platform-settings-driven execution model
- remove assumptions about pre-existing PDB paths
- call the same LocalColabFold and local Foldseek stages as the control plane

### `src/thermo_mining/config.py`

- stop being the active source of runtime truth
- either become a thin compatibility wrapper or be removed if no longer needed

### New step module

Add a new stage module for LocalColabFold structure generation, for example:

- `src/thermo_mining/steps/structure_predict.py`

Responsibilities:

- split retained FASTA into per-protein queries
- run LocalColabFold
- normalize PDB outputs
- emit `structure_manifest.json`
- write `DONE.json`

### `src/thermo_mining/steps/foldseek_client.py`

Replace HTTP-client behavior with local-binary behavior. The file can be kept
or renamed, but the active implementation must no longer depend on `requests`
or `base_url`.

### Config files

Update:

- `config/platform.example.yaml`
- `config/platform.server.ubuntu.yaml`

The Ubuntu draft should carry the real server paths for:

- `colabfold_batch_bin`
- `colabfold_data_dir`
- `foldseek_bin`
- `foldseek_database_path`

## Error Handling

### Structure Prediction

Fail `structure_predict` when:

- LocalColabFold exits non-zero
- no PDB is produced for a protein
- multiple ambiguous candidate PDBs exist for a protein
- required binaries or data roots are missing

The exception message must identify the failing `protein_id`.

### Foldseek

Fail `foldseek_confirm` when:

- Foldseek exits non-zero
- the configured database path does not exist
- a query result file cannot be parsed as expected

If a query returns no passing structural hits, that is not an execution error;
its summarized score is `0.0`.

## Testing Strategy

### Settings Tests

Add coverage for:

- new ColabFold tool fields
- new Foldseek binary fields
- new ColabFold defaults
- removal or migration of old Foldseek service-name assumptions

### Stage Graph Tests

Add coverage proving:

- `structure_predict` is inserted before `foldseek_confirm`
- stage numbering and suffixes reflect the new order

### LocalColabFold Step Tests

Add coverage proving:

- command construction includes `--data`, `--msa-mode`, `--num-models`,
  `--num-recycle`
- per-protein query FASTA files are written
- successful output normalization writes `structures/<protein_id>.pdb`
- manifest generation is deterministic
- missing or ambiguous PDB outputs fail correctly

### Foldseek Binary Step Tests

Add coverage proving:

- Foldseek command construction uses `easy-search`
- `foldseek_database_path` is passed instead of `base_url`
- `alntmscore` parsing and `min_tmscore` filtering behave correctly
- no-hit cases produce `0.0`

### Control Plane Runner Tests

Add coverage proving:

- the runner invokes `structure_predict` between ProTrek and Foldseek
- Foldseek consumes the structure manifest from the new stage
- runtime fields come from `load_settings()`

### CLI / Pipeline Tests

Add coverage proving:

- `thermo-mining run --config` now expects platform config
- CLI output roots resolve under `runtime.runs_root`
- the CLI path executes LocalColabFold and local Foldseek stages

## Migration Notes

- Existing run directories using the old stage numbering are not guaranteed to
  resume correctly after this change.
- Existing platform configs must be updated to add LocalColabFold and local
  Foldseek fields.
- AlphaFold parameter caches remain operator-managed assets outside git.
- The local Windows directory
  `D:\mining-agent\alphafold_params_2022-12-06` remains an operator artifact
  and is not part of repo cleanup or deletion work.

## Success Criteria

This change is successful when:

- the repo has a real structure-generation stage rather than assumed PDB paths
- Foldseek no longer requires an HTTP service
- both `thermo-mining run` and `thermo-mining run-job` use platform settings
- LocalColabFold and Foldseek runtime paths are fully configurable
- normalized `structures/*.pdb` outputs exist before Foldseek runs
- tests cover the new stage ordering, command construction, and score parsing
- the server-specific config can express the actual Ubuntu deployment layout

## Follow-Up Work

After this lands, the repo should be functionally server-runnable for the main
pipeline path. Remaining cleanup can then be narrowed to:

- ProTrek `weights_dir` naming cleanup if a path/file distinction still causes
  confusion
- documentation polish and operational runbook updates
- optional performance improvements for batch structure prediction
