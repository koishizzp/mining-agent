# Context Handoff: Seeded Mining Implementation

**Status:** paused
**Created:** 2026-04-02
**Updated:** 2026-04-04

## What We're Building

We implemented the approved seeded mining mode for the thermo-mining repo.
The seeded runtime adds a `seeded_proteins` contract that accepts one
`seed_faa` and one `target_faa`, runs seed-guided sequence recall, structure
recall, merge/reporting, seeded CLI execution, and control-plane runner
execution before feeding recalled targets into the existing thermo-mining
cascade.

As of 2026-04-04, the implementation work is complete through Task 7, has been
merged locally into `main`, and passes the full local test suite. The next
session should treat this as a deployment / server smoke-test checkpoint, not
as an unfinished coding checkpoint.

## Current State

### Completed

- [x] Task 1: seeded runtime contract, seeded defaults, stage order, and stage
  suffixes
  - Commit: `5bca697`
- [x] Task 2: planner support for `seed_paths`
  - Commit: `5eee6d2`
- [x] Task 3: seed sequence recall stage
  - Commit: `a7e0c0a`
  - Re-verified locally on 2026-04-04:
    - `pytest tests/steps/test_seed_sequence_recall.py -v`
    - observed: `2 passed`
- [x] Task 4: seed structure recall stage
  - Commit: `0bb09a4`
- [x] Task 5: seed merge plus seed-aware reporting
  - Commit: `0c061a5`
- [x] Task 6: seeded CLI pipeline and seeded resume path
  - Commit: `78bd90d`
- [x] Task 7: control-plane runner integration for the seeded stage graph
  - Commit: `9b1a59c`
- [x] Seeded implementation merged locally back into `main`
  - Merge mode: fast-forward
  - Feature worktree removed:
    - `D:\mining-agent\.worktrees\feat-seeded-mining`
  - Feature branch removed:
    - `feat/seeded-mining`
- [x] Post-merge local verification completed on `D:\mining-agent`
  - `pytest -q`
  - observed on 2026-04-04: `154 passed in 3.14s`

### In Progress

- [ ] Deployment / server validation
  - Local `main` contains the seeded runtime
  - Local `main` is still ahead of `origin/main`
  - No push has been done yet
  - No server-side `git pull` or seeded smoke test has been run yet

### Not Started

- [ ] Push merged `main` to remote
- [ ] Pull updated `main` on the server clone
- [ ] Run first real seeded smoke test on the server

## Key Files

| File | Role | Status |
|------|------|--------|
| [D:\mining-agent\docs\superpowers\specs\2026-04-02-thermo-mining-seeded-mining-design.md](D:/mining-agent/docs/superpowers/specs/2026-04-02-thermo-mining-seeded-mining-design.md) | Approved seeded mining design | Current |
| [D:\mining-agent\docs\superpowers\plans\2026-04-02-thermo-mining-seeded-mining-implementation-plan.md](D:/mining-agent/docs/superpowers/plans/2026-04-02-thermo-mining-seeded-mining-implementation-plan.md) | Task-by-task execution plan | Current |
| [D:\mining-agent\src\thermo_mining\pipeline.py](D:/mining-agent/src/thermo_mining/pipeline.py) | Seeded CLI runtime and short-circuit logic | Done |
| [D:\mining-agent\src\thermo_mining\control_plane\runner.py](D:/mining-agent/src/thermo_mining/control_plane/runner.py) | Seeded control-plane execution path | Done |
| [D:\mining-agent\src\thermo_mining\steps\seed_sequence_recall.py](D:/mining-agent/src/thermo_mining/steps/seed_sequence_recall.py) | Seed sequence recall stage | Done |
| [D:\mining-agent\src\thermo_mining\steps\seed_structure_recall.py](D:/mining-agent/src/thermo_mining/steps/seed_structure_recall.py) | Seed structure recall stage | Done |
| [D:\mining-agent\src\thermo_mining\steps\seed_recall_merge.py](D:/mining-agent/src/thermo_mining/steps/seed_recall_merge.py) | Seed hit merge and seeded target FASTA generation | Done |
| [D:\mining-agent\tests\test_pipeline_cli.py](D:/mining-agent/tests/test_pipeline_cli.py) | Seeded CLI / pipeline coverage | Passing |
| [D:\mining-agent\tests\control_plane\test_runner.py](D:/mining-agent/tests/control_plane/test_runner.py) | Seeded runner coverage | Passing |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Use a dedicated worktree during implementation | Keep seeded work isolated from `main` while Tasks 1-7 were landing |
| Merge back to `main` locally only after full Task 7 completion and full-suite verification | Avoid claiming seeded runs were ready before runner integration existed |
| Keep the existing thermo score formula unchanged while only adding seed provenance fields | Approved design required seed metadata without changing ranking semantics |
| Treat the next session as deployment / smoke test work instead of more coding | All planned implementation tasks are complete locally |

## Blockers / Open Questions

- The code is not yet on `origin/main`; local `main` is ahead of remote
- The server clone has not pulled the new commits yet
- The server-side tool/config paths for the first seeded smoke test have not
  been re-verified in this session
- No real seeded run has been executed on the server yet, so runtime readiness
  is still "locally verified, server unproven"

## What to Do Next

1. Push the locally merged `main` branch:

```bash
cd /d D:\mining-agent
git push origin main
```

2. On the server clone, pull the updated branch:

```bash
git pull origin main
```

3. Before the first seeded smoke test, confirm the server config still points
   at real installed tools for:
   - MMseqs2
   - TemStaPro
   - ProTrek
   - LocalColabFold
   - Foldseek

4. Run the first real seeded smoke test from the server clone using the merged
   `main` branch, then inspect the seeded stage outputs and final report.

## Gotchas

- The old implementation resume path in
  `D:\mining-agent\.worktrees\feat-seeded-mining` no longer exists; that
  worktree was intentionally removed after the local merge
- `main` currently has local documentation-state changes unrelated to the
  seeded code merge:
  - modified: [D:\mining-agent\STATE.md](D:/mining-agent/STATE.md)
  - untracked: [D:\mining-agent\docs\superpowers\2026-04-02-seeded-mining-implementation-handoff.md](D:/mining-agent/docs/superpowers/2026-04-02-seeded-mining-implementation-handoff.md)
  - untracked: [D:\mining-agent\docs\superpowers\plans\2026-04-02-thermo-mining-seeded-mining-implementation-plan.md](D:/mining-agent/docs/superpowers/plans/2026-04-02-thermo-mining-seeded-mining-implementation-plan.md)
- The seeded runtime is locally tested and merged, but not yet pushed or
  smoke-tested on the server; "can be deployed" is true, "already proven on the
  server" is not
