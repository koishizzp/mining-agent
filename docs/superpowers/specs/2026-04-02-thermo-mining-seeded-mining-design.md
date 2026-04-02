# Thermo Mining Seeded Mining Design

## Goal

Add an explicit seed-guided mining mode that accepts one seed FASTA and one
target FASTA, performs dual recall on the compressed target protein set through
both sequence and structure similarity, merges the recalled candidates by
union, and then sends only those retained target proteins through the existing
thermo-mining cascade.

After this change, the repo should be able to use a server-side seed file such
as `cas_seed_queries.faa` to mine a separate target protein collection rather
than treating the seed file itself as the candidate pool.

## Context

Current repo behavior is still single-input:

- `thermo-mining run` accepts one `--input-faa` path and treats that file as
  the protein set to filter and rank.
- The control plane likewise models one bundle whose `input_paths` are the
  direct candidate inputs.
- `ProTrek` currently indexes the current input FASTA and ranks it against
  configured text queries such as `thermostable enzyme`.
- `structure_predict` and `foldseek_confirm` now exist for the main pipeline,
  but they operate on proteins already retained by the thermo-mining cascade.
- There is no tracked runtime contract for `seed_faa -> target_faa` mining.

That means the repo cannot currently express the workflow the user wants:

1. choose one seed FASTA, for example `cas_seed_queries.faa`
2. choose a different target FASTA to mine
3. recall target candidates based on seed similarity
4. pass those recalled targets into the existing thermo-centric ranking stages

## Scope

### In scope

- Add a dedicated seeded mining mode for one seed FASTA plus one target FASTA
- Add a canonical stage graph for seeded protein runs
- Add sequence-based seed recall on clustered target representatives
- Add structure-based seed recall on clustered target representatives
- Merge both recall channels by union and emit a deterministic seed manifest
- Feed the merged target subset into the existing thermo-mining downstream
  stages
- Surface seed provenance in the final report outputs
- Add configuration defaults and tests for the seeded mode
- Support seeded runs through the CLI and control-plane plan / run contracts

### Out of scope

- Multiple seed FASTA files in one run
- Directory scanning or multi-file target bundle discovery
- Seeded variants of `paired_fastq` or `contigs` bundles
- Expanding clustered representative hits back to every cluster member
- Folding seed recall scores directly into the final thermo ranking formula
- Silent downgrade from dual recall to sequence-only recall when structure
  recall fails
- Rich browser-console UX for assembling seeded bundles; v1 only needs backend
  support and explicit CLI / API contracts

## Locked Decisions

- Introduce a new bundle type named `seeded_proteins`; do not overload the
  meaning of the existing `proteins` bundle type.
- Add a dedicated CLI entry point `thermo-mining run-seeded`; do not repurpose
  `thermo-mining run --input-faa` for dual-input behavior.
- V1 accepts exactly one `seed_faa` absolute path and exactly one `target_faa`
  absolute path.
- Run both seed recall channels only after `prefilter` and `mmseqs_cluster`
  compress the target set.
- Merge seed recall channels by union, not intersection.
- Record all matched seed IDs, the merged recall channel label
  (`sequence`, `structure`, or `both`), and the best score from each channel.
- Keep the existing thermo / ProTrek / Foldseek ranking formula as the final
  ordering function; seed recall acts as a candidate gate and provenance layer,
  not a direct score term.
- Final `foldseek_confirm` remains the global confirmation stage against the
  configured external structural database path.
- Seed structure recall must build its own local temporary Foldseek database
  from predicted target representative structures; it must not query the
  configured AFDB database used by final confirmation.
- If merged seed recall yields zero candidates, the seeded run should succeed
  with an empty report and skip the downstream thermo stages.

## Architecture

### Seeded Runtime Contract

The seeded mode introduces a dual-input contract:

- `seed_faa`
  - one FASTA containing the operator-chosen seed proteins
- `target_faa`
  - one FASTA containing the proteins to mine

The existing single-input modes remain unchanged:

- `thermo-mining run`
- control-plane `bundle_type: proteins`

The seeded mode becomes a separate runtime path:

- `thermo-mining run-seeded`
- control-plane `bundle_type: seeded_proteins`

This preserves the current behavior for non-seeded runs while making the new
mode explicit and testable.

### Control-Plane Bundle Shape

`InputBundle` should grow an explicit `seed_paths` field:

- default: empty list
- required for `seeded_proteins`
- forbidden for `proteins`, `contigs`, and `paired_fastq`

Validation rules:

- `seeded_proteins`
  - `len(seed_paths) == 1`
  - `len(input_paths) == 1`
  - all paths must be absolute
- `proteins`
  - `len(input_paths) == 1`
  - `seed_paths` must be empty
- `contigs`
  - `len(input_paths) == 1`
  - `seed_paths` must be empty
- `paired_fastq`
  - `len(input_paths) == 2`
  - `seed_paths` must be empty

The planner must include `seed_paths` in:

- bundle signatures used for plan validation
- the user prompt shown to the planner model
- fallback plan serialization

No new filesystem browsing API is required because the repo already exposes
server-path listing and search endpoints. A later browser-console change can
reuse those endpoints to populate the new seed path field.

## Stage Graph

### Bundle Type

Add a new bundle type:

- `seeded_proteins`

### Canonical Stage Order

The seeded stage graph should be:

- `prefilter`
- `mmseqs_cluster`
- `seed_sequence_recall`
- `seed_structure_recall`
- `seed_recall_merge`
- `temstapro_screen`
- `protrek_recall`
- `structure_predict`
- `foldseek_confirm`
- `rerank_report`

This keeps the existing thermo-centric cascade intact while inserting seeded
recall only once, immediately after the target set is compressed.

### Stage Directory Numbering

The numbered layout for a seeded run becomes:

- `01_prefilter`
- `02_cluster`
- `03_seed_sequence`
- `04_seed_structure`
- `05_seed_merge`
- `06_temstapro`
- `07_protrek`
- `08_structure`
- `09_foldseek`
- `10_report`

These suffixes should be added to `stage_layout.py`.

## Configuration Additions

No new `tools` fields are required. The seeded mode should reuse:

- `mmseqs_bin`
- `colabfold_batch_bin`
- `colabfold_data_dir`
- `foldseek_bin`

Add these new `defaults` fields:

- `seed_sequence_min_seq_id`
  - default: `0.30`
- `seed_sequence_coverage`
  - default: `0.80`
- `seed_sequence_topk_per_seed`
  - default: `200`
- `seed_structure_min_tmscore`
  - default: `0.55`
- `seed_structure_topk_per_seed`
  - default: `200`
- `seed_structure_max_targets`
  - default: `500`

Rationale:

- sequence recall should be permissive enough to surface remote homologs
  without collapsing into unbounded noise
- structure recall should remain slightly more permissive than the final
  `foldseek_confirm` gate because it is a recall stage, not the final
  confirmation stage
- structure recall needs an explicit safety cap because LocalColabFold remains
  the most expensive part of the seeded gate

## Seeded Data Flow

The seeded flow is:

1. read `target_faa`
2. run `prefilter`
3. run `mmseqs_cluster`
4. run `seed_sequence_recall` against cluster representatives
5. run `seed_structure_recall` against the same representatives
6. merge by union into `seed_manifest.tsv` plus `seeded_targets.faa`
7. if the merged set is empty:
   - write an empty report
   - mark the run successful
   - skip `temstapro_screen` onward
8. otherwise run:
   - `temstapro_screen`
   - `protrek_recall`
   - `structure_predict`
   - `foldseek_confirm`
   - `rerank_report`

The target set is the only dataset that flows into the thermo-mining scoring
stages. Seeds influence recall and provenance only.

## Stage Designs

### `seed_sequence_recall`

Add a new step module, for example:

- `src/thermo_mining/steps/seed_sequence_recall.py`

Inputs:

- `seed_faa`
- clustered representative FASTA from `mmseqs_cluster`
- `mmseqs_bin`
- sequence recall defaults

Suggested command shape:

```bash
<mmseqs_bin> easy-search \
  <seed_faa> \
  <cluster_rep_faa> \
  <raw_tsv> \
  <tmp_dir> \
  --min-seq-id <seed_sequence_min_seq_id> \
  -c <seed_sequence_coverage> \
  --cov-mode 1 \
  --max-seqs <seed_sequence_topk_per_seed> \
  --format-output query,target,pident
```

Stage outputs:

- `raw.tsv`
- `sequence_hits.tsv`
- `DONE.json`

`sequence_hits.tsv` must contain:

- `target_id`
- `seed_id`
- `sequence_score`

`sequence_score` is defined as `pident / 100.0`, rounded to four decimals.

This stage keeps one row per `(target_id, seed_id)` hit rather than collapsing
immediately, because the merge stage needs the full seed membership set.

### `seed_structure_recall`

Add a new step module, for example:

- `src/thermo_mining/steps/seed_structure_recall.py`

Inputs:

- `seed_faa`
- clustered representative FASTA from `mmseqs_cluster`
- `colabfold_batch_bin`
- `colabfold_data_dir`
- `foldseek_bin`
- structure recall defaults

Runtime behavior:

1. count clustered target representatives
2. fail early if the count exceeds `seed_structure_max_targets`
3. predict normalized seed structures
4. predict normalized target representative structures
5. build a stage-local Foldseek database from the normalized target structures
6. query every normalized seed PDB against that local database
7. summarize one row per `(target_id, seed_id)` pair

The prediction sub-steps should reuse the same per-protein LocalColabFold
normalization rule already used by `structure_predict`:

- one query FASTA per protein
- one normalized `structures/<protein_id>.pdb`
- fail if no unique PDB can be chosen

The local database is private to this stage and should live under the stage
directory, for example:

- `target_db/`

Suggested Foldseek query shape:

```bash
<foldseek_bin> easy-search \
  <seed_pdb> \
  <target_structure_db> \
  <seed_result_tsv> \
  <tmp_dir> \
  --format-output query,target,alntmscore \
  --max-seqs <seed_structure_topk_per_seed>
```

Stage outputs:

- `seed_structures/`
- `target_structures/`
- `raw/`
- `structure_hits.tsv`
- `DONE.json`

`structure_hits.tsv` must contain:

- `target_id`
- `seed_id`
- `structure_score`

`structure_score` is defined as the best surviving `alntmscore` for that
`(target_id, seed_id)` pair after filtering out hits below
`seed_structure_min_tmscore`.

### `seed_recall_merge`

Add a new step module, for example:

- `src/thermo_mining/steps/seed_recall_merge.py`

Inputs:

- clustered representative FASTA
- `sequence_hits.tsv`
- `structure_hits.tsv`

Merge rules:

- keep the union of target IDs from both hit tables
- `seed_ids` is the sorted union of all matching seed IDs across both channels
- `seed_channels`
  - `sequence` if only the sequence table matched
  - `structure` if only the structure table matched
  - `both` if both tables matched
- `best_sequence_score` is the maximum sequence score for that target, else
  `0.0`
- `best_structure_score` is the maximum structure score for that target, else
  `0.0`

Stage outputs:

- `seed_manifest.tsv`
- `seeded_targets.faa`
- `DONE.json`

`seed_manifest.tsv` must contain:

- `target_id`
- `seed_ids`
- `seed_channels`
- `best_sequence_score`
- `best_structure_score`

`seeded_targets.faa` contains only the clustered representative target records
whose IDs appear in the merged manifest.

## Downstream Thermo Stages

After `seed_recall_merge`, the main pipeline should operate on
`seeded_targets.faa` instead of on the full clustered target representative
FASTA.

Downstream stages remain:

- `temstapro_screen`
- `protrek_recall`
- `structure_predict`
- `foldseek_confirm`
- `rerank_report`

This means v1 keeps the current thermo-mining semantics:

- thermo scoring still uses TemStaPro
- semantic reranking still uses ProTrek text queries
- final structural confirmation still uses the configured external Foldseek
  database

## Empty-Recall Short-Circuit

If `seed_recall_merge` produces zero retained targets, the seeded run should
not fail.

Instead:

- write an empty `seed_manifest.tsv`
- write an empty `seeded_targets.faa`
- write empty `top_100.tsv` and `top_1000.tsv` report files with headers only
- write a `summary.md` whose tier counts are all zero
- mark the run as succeeded
- do not run `temstapro_screen`, `protrek_recall`, `structure_predict`, or
  `foldseek_confirm`

This behavior is important because "no seed-guided hits survived" is a valid
scientific outcome, not an execution error.

## Reporting Contract

`rerank_report` should keep the current report layout but expand the TSV fields
for seeded runs.

Add these report fields:

- `seed_ids`
- `seed_channels`
- `best_sequence_score`
- `best_structure_score`

The final TSV order should become:

- `protein_id`
- `seed_ids`
- `seed_channels`
- `best_sequence_score`
- `best_structure_score`
- `thermo_score`
- `protrek_score`
- `foldseek_score`
- `origin_bonus`
- `final_score`
- `tier`

For non-seeded runs, these fields should still exist in report output for
schema stability, with empty `seed_ids`, empty `seed_channels`, and numeric
seed scores set to `0.0`.

`combine_stage_scores` should accept optional seed-support metadata and merge
it into each final row without changing the existing final-score formula.

For seeded runs, `hot_spring_ids` must still be computed from the original
`target_faa`, not from the seed FASTA.

## CLI And Control Plane

### CLI

Add a new subcommand:

```bash
thermo-mining run-seeded \
  --config <platform_yaml> \
  --run-name <run_name> \
  --seed-faa <seed_faa> \
  --target-faa <target_faa> \
  --resume
```

Notes:

- `--resume` should follow the same stage hash semantics as the existing
  `run` command
- output roots should still resolve under `settings.runtime.runs_root`
- the existing `run` subcommand remains unchanged

### Control Plane

The control-plane planner and runner must support:

- `bundle_type: seeded_proteins`
- `seed_paths: [<absolute_seed_faa>]`
- `input_paths: [<absolute_target_faa>]`

`build_stage_order()` must return the seeded stage graph for
`seeded_proteins`.

`run_job()` must detect the seeded bundle type and route execution through the
seeded stage path rather than the existing single-input protein path.

The plan API does not need a new route. It only needs the updated schema and
plan validation logic.

## File-Level Design Impact

### Modify

- `src/thermo_mining/cli.py`
  - add `run-seeded` CLI parsing
- `src/thermo_mining/settings.py`
  - add seeded recall defaults
- `src/thermo_mining/control_plane/schemas.py`
  - add `seeded_proteins`
  - add `seed_paths`
  - extend validation rules
- `src/thermo_mining/control_plane/stage_graph.py`
  - add seeded stage order
- `src/thermo_mining/control_plane/planner.py`
  - include `seed_paths` in prompts and bundle signatures
- `src/thermo_mining/control_plane/runner.py`
  - add seeded execution path and empty-recall short-circuit
- `src/thermo_mining/stage_layout.py`
  - add new stage suffixes
- `src/thermo_mining/pipeline.py`
  - add a seeded pipeline entry point or equivalent shared seeded execution path
- `src/thermo_mining/steps/rerank.py`
  - merge optional seed provenance into final rows
- `src/thermo_mining/reporting.py`
  - extend report schema and empty-report handling
- `config/platform.example.yaml`
  - document seeded defaults
- `config/platform.server.ubuntu.yaml`
  - document seeded defaults

### Create

- `src/thermo_mining/steps/seed_sequence_recall.py`
- `src/thermo_mining/steps/seed_structure_recall.py`
- `src/thermo_mining/steps/seed_recall_merge.py`

### Tests

- `tests/test_pipeline_cli.py`
- `tests/control_plane/test_schemas.py`
- `tests/control_plane/test_planner.py`
- `tests/control_plane/test_runner.py`
- `tests/steps/test_seed_sequence_recall.py`
- `tests/steps/test_seed_structure_recall.py`
- `tests/steps/test_seed_recall_merge.py`
- `tests/test_settings.py`

## Error Handling

Fail the seeded run when:

- `seed_faa` or `target_faa` does not exist
- `seed_faa` is empty
- `target_faa` is empty after `prefilter`
- clustered representative count exceeds `seed_structure_max_targets`
- sequence recall command execution fails
- structure prediction inside seed structure recall fails
- local Foldseek database creation or query execution fails
- merged seed manifest refers to a target ID not present in the clustered
  representative FASTA

Do not fail the run when:

- sequence recall returns zero hits but structure recall returns hits
- structure recall returns zero passing hits but sequence recall returns hits
- both recall channels return zero hits after successful execution

The final case must trigger the empty-report short-circuit.

## Testing Strategy

### Settings Tests

Add coverage proving:

- new seeded defaults load from YAML
- seeded defaults can be overridden from environment variables

### Schema Tests

Add coverage proving:

- `seeded_proteins` requires one absolute `seed_paths` item and one absolute
  `input_paths` item
- non-seeded bundles reject non-empty `seed_paths`

### Stage Graph Tests

Add coverage proving:

- `build_stage_order("seeded_proteins")` returns the canonical seeded order
- stage suffix numbering matches the seeded order

### Sequence Recall Tests

Add coverage proving:

- `mmseqs easy-search` command construction includes the seeded defaults
- raw hit parsing emits one row per `(target_id, seed_id)`
- `sequence_score` normalization is deterministic

### Structure Recall Tests

Add coverage proving:

- representative-count cap is enforced before structure prediction begins
- seed and target structure prediction reuse deterministic normalized PDB names
- local Foldseek database creation is stage-scoped
- per-seed Foldseek queries are built correctly
- per-pair score filtering by `seed_structure_min_tmscore` behaves correctly

### Merge Tests

Add coverage proving:

- union semantics across sequence and structure hits
- correct `seed_channels` labeling
- sorted `seed_ids` aggregation
- deterministic `seeded_targets.faa` generation

### Runner / Pipeline Tests

Add coverage proving:

- `run-seeded` routes into the seeded execution path
- the control-plane runner executes the seeded stage order for
  `seeded_proteins`
- empty merged recall short-circuits the downstream thermo stages
- seeded runs still use the existing downstream thermo steps once candidates
  exist
- seeded report rows include seed provenance fields

## Migration Notes

- Existing `proteins` runs remain unchanged and must not require a seed input.
- Existing reports should adopt the expanded column set for schema stability.
- Seed structure recall intentionally duplicates some structure work relative to
  final `structure_predict`; this is acceptable in v1 to keep recall and final
  confirmation contracts separate.
- Browser-console ergonomics for picking the seed path can follow later; the
  backend contract must be complete first.

## Success Criteria

This change is successful when:

- the repo can accept one seed FASTA and one target FASTA as separate inputs
- target mining is driven by seed similarity rather than by treating the seed
  FASTA as the candidate pool
- both sequence and structure seed recall execute after target compression
- union-merged seed candidates feed into the existing thermo-mining cascade
- final reports expose `seed_ids`, recall channels, and best per-channel scores
- zero-hit seeded runs produce empty reports rather than failed runs
- non-seeded runs keep their existing behavior
