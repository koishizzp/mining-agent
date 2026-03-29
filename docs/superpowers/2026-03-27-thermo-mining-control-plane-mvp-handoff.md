# Context Handoff: Thermo Mining Control Plane MVP

**Status:** paused
**Created:** 2026-03-27

## What We're Building

We are implementing the control-plane MVP for the thermo mining platform on top of the existing
`thermo_mining` pipeline. Success means the repo gains a single-user FastAPI control plane with
chat-driven planning, server-side path browsing, plan review, tmux-backed execution, run
monitoring, artifact browsing, and a restricted OpenAI-compatible chat API, following the approved
spec and implementation plan.

## Current State

### Completed
- [x] Control-plane MVP spec written and committed on `main`
  - Spec file: [2026-03-27-thermo-mining-control-plane-mvp-design.md](/D:/mining-agent/docs/superpowers/specs/2026-03-27-thermo-mining-control-plane-mvp-design.md)
  - Commit: `3c33dbd`
- [x] Control-plane MVP implementation plan written and committed on `main`
  - Plan file: [2026-03-27-thermo-mining-control-plane-mvp.md](/D:/mining-agent/docs/superpowers/plans/2026-03-27-thermo-mining-control-plane-mvp.md)
  - Commit: `2109028`
- [x] Isolated worktree created for implementation
  - Worktree path: `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp`
  - Branch: `feat/thermo-mining-control-plane-mvp`
  - `safe.directory` was added globally for this worktree so git operations work under this environment
- [x] Task 1 finished and fully reviewed
  - Goal: bootstrap control-plane settings and CLI command parsing
  - Commits on feature branch:
    - `931185f` `build(control-plane): bootstrap settings and cli`
    - `b666c91` `fix(control-plane): fail loudly for unwired cli commands`
    - `0202be8` `test(control-plane): restore parser acceptance assertions`
  - Task 1 review status:
    - Spec review: passed
    - Code quality review: passed
  - Verification evidence:
    - `pytest tests/test_control_plane_bootstrap.py -v`
    - `pytest -q`
    - Last reported full-suite result after Task 1: `33 passed in 0.41s`
- [x] Task 2 implementation code has been written and committed by implementer subagent
  - Commit: `f393e5c` `feat(control-plane): add schemas and stage graph`
  - Files added:
    - [__init__.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/__init__.py)
    - [schemas.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/schemas.py)
    - [stage_graph.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/stage_graph.py)
    - [test_schemas.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/tests/control_plane/test_schemas.py)

### In Progress
- [ ] Task 2 is not review-complete yet
  - The implementer finished and committed `f393e5c`
  - Only targeted test evidence was reported:
    - RED: `pytest tests/control_plane/test_schemas.py -v` failed with `ModuleNotFoundError`
    - GREEN: `pytest tests/control_plane/test_schemas.py -v` passed with `3 passed`
  - Spec compliance review for Task 2 has **not** been run yet
  - Code quality review for Task 2 has **not** been run yet
  - Full `pytest -q` after Task 2 has **not** been re-verified in the controller session

### Not Started
- [ ] Task 3: absolute-path filesystem listing and search
- [ ] Task 4: FASTQ pairing and bundle scanning
- [ ] Task 5: pending runs, runtime state, and artifact listings
- [ ] Task 6: fastp / SPAdes / Prodigal adapter commands
- [ ] Task 7: bundle-aware runner
- [ ] Task 8: tmux-backed job manager
- [ ] Task 9: planner, fallback parsing, and failure explanation
- [ ] Task 10: filesystem and planning JSON APIs
- [ ] Task 11: run lifecycle and restricted chat APIs
- [ ] Task 12: web console, final CLI wiring, and deployment scripts

## Key Files

| File | Role | Status |
|------|------|--------|
| [spec](/D:/mining-agent/docs/superpowers/specs/2026-03-27-thermo-mining-control-plane-mvp-design.md) | Approved MVP scope and boundaries | Complete |
| [plan](/D:/mining-agent/docs/superpowers/plans/2026-03-27-thermo-mining-control-plane-mvp.md) | Task-by-task implementation plan | Complete |
| [pyproject.toml](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/pyproject.toml) | Dependencies and packaging config | Task 1 complete |
| [platform.example.yaml](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/config/platform.example.yaml) | Runtime example config | Task 1 complete |
| [settings.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/settings.py) | Typed settings | Task 1 complete |
| [cli.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/cli.py) | CLI parser bootstrap; `serve` / `run-job` currently fail loudly on purpose | Task 1 complete |
| [control_plane/__init__.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/__init__.py) | Control-plane package marker | Task 2 implemented |
| [schemas.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/schemas.py) | Pydantic models and constants | Task 2 implemented, not reviewed |
| [stage_graph.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/stage_graph.py) | Bundle-type stage order selection | Task 2 implemented, not reviewed |
| [test_control_plane_bootstrap.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/tests/test_control_plane_bootstrap.py) | Task 1 bootstrap tests | Complete and reviewed |
| [test_schemas.py](/D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/tests/control_plane/test_schemas.py) | Task 2 schema and stage graph tests | Implemented, not reviewed |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Use a dedicated worktree on branch `feat/thermo-mining-control-plane-mvp` | Keep control-plane work isolated from `main` and avoid mixing ongoing local files |
| Execute with `subagent-driven-development` | User explicitly chose Subagent-Driven execution after the plan was approved |
| Keep Task 1 `serve` / `run-job` commands as explicit fail-loudly placeholders | Avoid silent no-op behavior before Task 12 wires real execution paths |
| Keep `jinja2` dependency and `thermo_mining.web` package-data in Task 1 | The implementation plan explicitly required them; quality review concern was pushed back on that basis |
| Do not stage generated artifacts in the worktree | `.codex-wheelcheck/`, `build/`, and `src/thermo_mining.egg-info/` are unrelated generated files |

## Blockers / Open Questions

- Task 2 review loop is incomplete. Before moving to Task 3, someone must:
  - run a spec compliance review for Task 2
  - run a code quality review for Task 2
  - fix any issues found
- No blocker currently prevents continuing, but skipping the Task 2 review gate would violate the chosen workflow.

## What to Do Next

1. Resume in the feature worktree:
   - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp`
   - Confirm branch: `git status --short --branch`
2. Start from Task 2 review closure, not from Task 3:
   - Request spec compliance review for Task 2 against the Task 2 section of [plan](/D:/mining-agent/docs/superpowers/plans/2026-03-27-thermo-mining-control-plane-mvp.md)
   - If spec passes, request code quality review for Task 2
   - Fix any findings on the same branch before proceeding
3. Re-run verification after Task 2 review fixes:
   - `pytest tests/control_plane/test_schemas.py -v`
   - `pytest -q`
4. Only after Task 2 passes both reviews, dispatch Task 3 implementer subagent.

## Exact Commands

```powershell
git -C 'D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp' status --short --branch
git -C 'D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp' log --oneline --decorate -6
pytest tests/control_plane/test_schemas.py -v
pytest -q
```

## Gotchas

- The terminal session was interrupted while Task 2 execution was in progress. The implementer still completed and committed `f393e5c`; that commit is real and already on the feature branch.
- In this environment, git operations in the worktree often needed escalated permission because of worktree metadata lock/safe-directory constraints.
- `main` and the feature worktree are different contexts:
  - `main` contains the approved spec/plan commits
  - feature worktree contains implementation commits
- Root repo currently has unrelated untracked files:
  - `D:\mining-agent\.superpowers\`
  - `D:\mining-agent\2026-03-27-thermophile-mining-implementation-plan.md`
  - `D:\mining-agent\STATE.md`
- Feature worktree currently has unrelated generated untracked files:
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\.codex-wheelcheck\`
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\build\`
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining.egg-info\`
  Do not accidentally stage them.
- Do not treat Task 2 as finished just because `f393e5c` exists. Under the chosen workflow, a task is only done after:
  - implementer completion
  - spec compliance review pass
  - code quality review pass
