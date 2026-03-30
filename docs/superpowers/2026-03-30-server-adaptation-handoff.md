# Context Handoff: Thermo Mining Server Adaptation

**Status:** paused
**Created:** 2026-03-30

## What We're Building
We are finishing the server-specific deployment adaptation for the thermo
mining control plane on the Linux host rooted at `/mnt/disk3/tio_nekton4`.
The goal is to turn the already-implemented control plane into something that
can actually run against the user's real server toolchain by replacing
remaining hardcoded assumptions, preserving the probe workflow, and locking the
server configuration into repo-tracked artifacts.

## Current State
### Completed
- [x] Server probe utility implemented and merged on `main`
  - Probe script: [D:\mining-agent\scripts\server_probe.py](D:/mining-agent/scripts/server_probe.py)
  - Latest probe-related fixes already on `main`:
    - `9faf206` `feat(server-probe): report conda probe metadata`
    - `3097d8c` `fix(server-probe): skip inaccessible candidate paths`
    - `76c1cec` `fix(server-probe): resolve base conda env names`
- [x] Current server probe results downloaded locally
  - JSON: [D:\mining-agent\thermo_server_probe\server_probe.json](D:/mining-agent/thermo_server_probe/server_probe.json)
  - YAML draft: [D:\mining-agent\thermo_server_probe\platform.server-draft.yaml](D:/mining-agent/thermo_server_probe/platform.server-draft.yaml)
  - TXT summary: [D:\mining-agent\thermo_server_probe\server_probe.txt](D:/mining-agent/thermo_server_probe/server_probe.txt)
- [x] Ubuntu-specific platform draft prepared
  - Draft config: [D:\mining-agent\config\platform.server.ubuntu.yaml](D:/mining-agent/config/platform.server.ubuntu.yaml)
- [x] TemStaPro runtime design spec written
  - Spec: [D:\mining-agent\docs\superpowers\specs\2026-03-30-thermo-mining-temstapro-runtime-design.md](D:/mining-agent/docs/superpowers/specs/2026-03-30-thermo-mining-temstapro-runtime-design.md)
  - Commit: `abf079c`
- [x] Latest local verification of the codebase before stopping
  - `pytest -q`
  - Result observed earlier this session: `125 passed in 3.10s`

### In Progress
- [ ] Server runtime adaptation is only partially finished
  - TemStaPro still relies on hardcoded runtime values in the control-plane path
  - Foldseek still expects `tools.foldseek_base_url` rather than a local binary
  - ProTrek still uses a field named `protrek_weights_dir` even though the
    server currently exposes a single weights file

### Not Started
- [ ] TemStaPro runtime configuration implementation plan
- [ ] TemStaPro runtime code changes in `settings.py`, `runner.py`, and
  `temstapro_screen.py`
- [ ] Foldseek local-binary support or server-side Foldseek HTTP service setup
- [ ] ProTrek weights file vs. directory contract cleanup

## Key Files
| File | Role | Status |
|------|------|--------|
| [D:\mining-agent\scripts\server_probe.py](D:/mining-agent/scripts/server_probe.py) | Server probe used to inspect real Linux environment | Complete |
| [D:\mining-agent\config\platform.server.ubuntu.yaml](D:/mining-agent/config/platform.server.ubuntu.yaml) | Repo-tracked Ubuntu server config draft | Draft, incomplete |
| [D:\mining-agent\thermo_server_probe\server_probe.json](D:/mining-agent/thermo_server_probe/server_probe.json) | Canonical downloaded server probe artifact | Local, untracked |
| [D:\mining-agent\src\thermo_mining\control_plane\runner.py](D:/mining-agent/src/thermo_mining/control_plane/runner.py) | Control-plane runtime orchestration; still hardcodes TemStaPro model/cache paths | Needs work |
| [D:\mining-agent\src\thermo_mining\steps\temstapro_screen.py](D:/mining-agent/src/thermo_mining/steps/temstapro_screen.py) | TemStaPro subprocess command builder and executor | Needs runtime config support |
| [D:\mining-agent\src\thermo_mining\settings.py](D:/mining-agent/src/thermo_mining/settings.py) | Platform settings loader | Needs TemStaPro runtime fields |
| [D:\mining-agent\src\thermo_mining\steps\foldseek_client.py](D:/mining-agent/src/thermo_mining/steps/foldseek_client.py) | Foldseek HTTP client stage | Still requires `base_url` |
| [D:\mining-agent\src\thermo_mining\steps\protrek_bridge.py](D:/mining-agent/src/thermo_mining/steps/protrek_bridge.py) | ProTrek bridge layer | Still uses `weights_dir` naming |
| [D:\mining-agent\docs\superpowers\specs\2026-03-30-thermo-mining-temstapro-runtime-design.md](D:/mining-agent/docs/superpowers/specs/2026-03-30-thermo-mining-temstapro-runtime-design.md) | Approved design for the next TemStaPro-focused subproject | Current |

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Treat `/mnt/disk3/tio_nekton4` as the intended server repo root | The user explicitly said the server clone will live there |
| Prefer `/mnt/disk3/tio_nekton4/tmux-local/bin/tmux` over the Conda `tmux` | The probe surfaced a `libtinfo` warning on the Conda `tmux`, making the local custom build the safer runtime choice |
| Keep Foldseek unresolved in config draft instead of guessing | Current code expects an HTTP `foldseek_base_url`; only a local binary path is known so far |
| Keep `protrek_weights_dir` set to the observed `.pt` file in the config draft, but treat it as a known mismatch | The server provides `/mnt/disk3/tio_nekton4/ProTrek/ProTrek_650M.pt`, while current code and field naming imply a directory |
| Use probe output as the source of truth for server discovery, but keep `probe_thermo.sh` and downloaded artifacts untracked | They are local operator artifacts, not part of the reproducible repo state |
| Split TemStaPro runtime cleanup into its own spec before implementation | That is the highest-leverage remaining blocker and requires design-level choices (`conda run`, env vars, repo root, model/cache dirs) |

## Blockers / Open Questions
- TemStaPro is not yet deployable from platform config because:
  - `runner.py` still hardcodes `model_dir="/models/temstapro/ProtTrans"`
  - `runner.py` still hardcodes `cache_dir="/tmp/temstapro_cache"`
  - no config field yet exists for:
    - `conda_bin`
    - `temstapro_conda_env_name`
    - `temstapro_repo_root`
    - `temstapro_model_dir`
    - `temstapro_cache_dir`
    - `temstapro_hf_home`
    - `temstapro_transformers_offline`
- Foldseek is unresolved:
  - observed server binary: `/mnt/disk3/tio_nekton4/foldseek/bin/foldseek`
  - current code still requires `tools.foldseek_base_url`
- ProTrek semantics are unresolved:
  - observed server value: `/mnt/disk3/tio_nekton4/ProTrek/ProTrek_650M.pt`
  - current code passes this through a field named `weights_dir`
- Runtime roots are still defaults in the draft config:
  - `/mnt/disk3/tio_nekton4/inputs`
  - `/mnt/disk3/tio_nekton4/runs`
  - `/mnt/disk3/tio_nekton4/logs/platform.log`
  These are placeholders unless the user confirms repo-local storage is fine.

## What to Do Next
1. Write the implementation plan for the approved TemStaPro runtime design.
   - Source spec: [D:\mining-agent\docs\superpowers\specs\2026-03-30-thermo-mining-temstapro-runtime-design.md](D:/mining-agent/docs/superpowers/specs/2026-03-30-thermo-mining-temstapro-runtime-design.md)
2. Implement TemStaPro runtime configuration support in:
   - [D:\mining-agent\src\thermo_mining\settings.py](D:/mining-agent/src/thermo_mining/settings.py)
   - [D:\mining-agent\src\thermo_mining\steps\temstapro_screen.py](D:/mining-agent/src/thermo_mining/steps/temstapro_screen.py)
   - [D:\mining-agent\src\thermo_mining\control_plane\runner.py](D:/mining-agent/src/thermo_mining/control_plane/runner.py)
   - [D:\mining-agent\config\platform.example.yaml](D:/mining-agent/config/platform.example.yaml)
   - [D:\mining-agent\config\platform.server.ubuntu.yaml](D:/mining-agent/config/platform.server.ubuntu.yaml)
3. Re-run tests after that implementation:
   - `pytest tests/test_settings.py -v`
   - `pytest tests/control_plane/test_runner.py -v`
   - `pytest tests/steps/test_temstapro_screen.py -v`
   - `pytest -q`
4. After TemStaPro is configurable, choose the next server blocker:
   - Foldseek local-binary support in the control plane
   - or explicit Foldseek HTTP service deployment on the server
5. Only after those runtime blockers are cleared should the repo be treated as
   genuinely server-runnable.

## Gotchas
- Local probe artifacts remain untracked:
  - `D:\mining-agent\thermo_server_probe\`
  - `D:\mining-agent\probe_thermo.sh`
- The current repo already contains a detached leftover worktree:
  - `D:\mining-agent\.worktrees\server-probe-conda-parent-review`
  It is not the main implementation line, but it still appears in `git worktree list`.
- Root repo is still ahead of `origin/main`; no network sync has been performed in this session.
- The probe now correctly resolves Conda base prefixes and skips inaccessible candidate paths, so future probe reruns should use:

```bash
python3 ~/server_probe.py --output-dir ~/thermo_server_probe --conda-prefix /mnt/disk3/tio_nekton4/miniconda3
```

- The TemStaPro manual working invocation the user reported is:

```bash
conda activate temstapro_env_CPU
export TRANSFORMERS_OFFLINE=1
export HF_HOME=/mnt/disk3/tio_nekton4/.cache/huggingface
cd /mnt/disk3/tio_nekton4/TemStaPro-main
./temstapro -f tests/data/multiple_short_sequences.fasta -d ./models -e ./cache --mean-output test.tsv
```

That command is the ground truth for the upcoming runtime configuration work.
