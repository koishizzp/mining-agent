# Context Handoff: Thermo Mining Control Plane MVP Final State

**Status:** paused
**Created:** 2026-03-28
**Updated:** 2026-03-30

## What We're Building
This branch implements the thermo mining control-plane MVP on top of the
existing `thermo_mining` pipeline: server-side path browsing, planning,
review/edit flow, tmux-backed execution, run monitoring, artifact access,
restricted chat behavior, and a minimal single-page console. The branch is
functionally complete through Task 12 and now has the late strict-cleanup
layer committed as well.

## Current State
### Completed
- [x] Tasks 1 through 12 are implemented on
  `feat/thermo-mining-control-plane-mvp`
  - Major delivery sequence ends at `94b4e12`
- [x] Strict-cleanup compatibility layer is committed
  - Commit: `e509196` `fix(control-plane): preserve cleanup compatibility`
  - Scope:
    - direct `OpenAI` import with lazy client construction still preserved
    - `Jinja2Templates` page rendering using the current Starlette call shape
    - README, HTML, CSS, and JS pulled closer to the original Task 10 / 12
      snippet shapes without losing viewport/mobile/newline behavior
    - regression coverage for no-key planner fallback and page/static checks
- [x] Fresh local verification passed before handoff
  - `pytest tests/control_plane/test_planner.py tests/web/test_fs_and_plan_api.py tests/web/test_pages.py -q`
    -> `20 passed in 2.36s`
  - `pytest -q`
    -> `110 passed in 3.15s`

### In Progress
- [ ] Branch integration decision is still open
  - Base branch is still `main`
  - No PR has been created

### Not Started
- [ ] Linux-side smoke execution of:
  - `scripts/start_web.sh`
  - `scripts/start_all.sh`
  - `scripts/status.sh`
  - `scripts/stop.sh`
- [ ] Manual browser/API smoke on a real served instance

## Key Files
| File | Role | Status |
|------|------|--------|
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\control_plane\runner.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/runner.py) | Bundle-aware execution orchestration | Complete |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\control_plane\job_manager.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/job_manager.py) | Active-run lock and tmux lifecycle | Complete |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\control_plane\planner.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/planner.py) | LLM and fallback planning | Complete |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\control_plane\llm_client.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/control_plane/llm_client.py) | OpenAI responses client wrapper | Updated in `e509196` |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\web\routes_pages.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/web/routes_pages.py) | Console page route | Updated in `e509196` |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining\web\templates\index.html](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/src/thermo_mining/web/templates/index.html) | Single-page console shell | Updated in `e509196` |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\tests\web\test_fs_and_plan_api.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/tests/web/test_fs_and_plan_api.py) | Plan API regression coverage | Updated in `e509196` |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\tests\web\test_pages.py](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/tests/web/test_pages.py) | Page/static regression coverage | Updated in `e509196` |
| [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\docs\superpowers\2026-03-28-thermo-mining-control-plane-mvp-final-handoff.md](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp/docs/superpowers/2026-03-28-thermo-mining-control-plane-mvp-final-handoff.md) | Session recovery handoff | Current |

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Keep the late practical hardening from Tasks 10 to 12 instead of reverting fully to snippet form | The hardened web/API behavior closes real runtime defects that the exact snippets would leave open |
| Commit the strict-cleanup layer instead of leaving it as an uncommitted tail | The diff is coherent, covered by fresh tests, and easier to integrate once captured in git history |
| Preserve lazy OpenAI client construction even with direct `openai` import restored | Eager client construction breaks the fallback planner path when API keys are absent |
| Use `TemplateResponse(request, "index.html")` | Keeps template rendering current and avoids the deprecated signature path |
| Leave generated directories untracked | They are environment artifacts, not source changes |

## Blockers / Open Questions
- Integration choice is still open: merge locally, push a PR, keep the branch,
  or discard it later.
- Linux deployment smoke has not been run from this Windows environment.
- No manual browser smoke has been run after the final cleanup commit; current
  confidence comes from tests and static inspection.

## What to Do Next
1. Resume in the feature worktree and inspect current branch state.
   - `git -C D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp status --short --branch`
   - `git -C D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp log --oneline --decorate -5`
2. Decide integration path for `feat/thermo-mining-control-plane-mvp`.
3. Before merge or PR, rerun:
   - `pytest -q`
4. In the Linux deployment environment, run:
   - `bash scripts/start_web.sh`
   - `bash scripts/status.sh`
   - `bash scripts/stop.sh`
5. If doing a manual smoke, serve the app and hit:
   - `/`
   - `/api/fs/list`
   - `/api/plan`
   - `/api/runs/active`
   - `/v1/chat/completions`

## Gotchas
- Current branch root is
  [D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp](D:/mining-agent/.worktrees/thermo-mining-control-plane-mvp),
  not `D:\mining-agent`.
- Generated untracked paths still exist in the worktree:
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\.codex-wheelcheck\`
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\build\`
  - `D:\mining-agent\.worktrees\thermo-mining-control-plane-mvp\src\thermo_mining.egg-info\`
- The latest meaningful source commit is `e509196`.
- Current local environment has `openai==2.30.0` and `jinja2==3.1.6`
  installed.
