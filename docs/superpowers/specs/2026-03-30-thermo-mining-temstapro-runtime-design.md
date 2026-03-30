# Thermo Mining TemStaPro Runtime Configuration Design

## Goal

Remove the remaining TemStaPro deployment blockers from the control-plane
runtime by replacing hardcoded TemStaPro paths and shell assumptions with
explicit server configuration. After this change, the control plane should be
able to run the TemStaPro stage on the target server through configured paths
and `conda run`, without relying on manual `conda activate` or hardcoded model
locations in the code.

## Context

The current server probe and manual server inspection established these facts:

- TemStaPro is available at:
  - `/mnt/disk3/tio_nekton4/TemStaPro-main/temstapro`
- The TemStaPro runtime currently works when the user runs:
  - `conda activate temstapro_env_CPU`
  - `export TRANSFORMERS_OFFLINE=1`
  - `export HF_HOME=/mnt/disk3/tio_nekton4/.cache/huggingface`
  - `cd /mnt/disk3/tio_nekton4/TemStaPro-main`
  - `./temstapro -f ... -d ./models -e ./cache --mean-output ...`
- The current control-plane runner still hardcodes:
  - `model_dir="/models/temstapro/ProtTrans"`
  - `cache_dir="/tmp/temstapro_cache"`
- The current code does not know:
  - which Conda executable to use
  - which Conda environment name to run
  - which working directory to use for TemStaPro
  - which `HF_HOME` / offline flags to inject

That means the repo is still not server-complete even though the TemStaPro
binary path is known.

## Scope

### In scope

- Add explicit TemStaPro runtime fields to platform settings
- Load those fields from YAML and environment variables
- Update the control-plane runner to use configured TemStaPro values
- Update TemStaPro command execution so it can run through `conda run -n ...`
- Pass TemStaPro-specific environment variables and working directory
- Update tests and example/server config files

### Out of scope

- Installing TemStaPro or its Conda environment
- Verifying or downloading Hugging Face model assets
- Changing Foldseek from HTTP mode to local-binary mode
- Fixing ProTrek `weights_dir` semantics
- Auto-detecting TemStaPro model or cache paths

## Locked Decisions

- Use `conda run -n <env_name>` rather than `conda activate ...`
- Keep TemStaPro runtime configuration under `tools` in the platform config
- Do not hardcode server-specific TemStaPro paths in Python source
- Continue treating TemStaPro runtime as a configured deployment concern
- Keep Foldseek and ProTrek follow-up work separate from this change

## Configuration Additions

Add these new `tools` fields:

- `conda_bin`
  - Example:
    - `/mnt/disk3/tio_nekton4/miniconda3/bin/conda`
- `temstapro_conda_env_name`
  - Example:
    - `temstapro_env_CPU`
- `temstapro_repo_root`
  - Example:
    - `/mnt/disk3/tio_nekton4/TemStaPro-main`
- `temstapro_model_dir`
  - Example:
    - `/mnt/disk3/tio_nekton4/TemStaPro-main/models`
- `temstapro_cache_dir`
  - Example:
    - `/mnt/disk3/tio_nekton4/TemStaPro-main/cache`
- `temstapro_hf_home`
  - Example:
    - `/mnt/disk3/tio_nekton4/.cache/huggingface`
- `temstapro_transformers_offline`
  - Example:
    - `true`

These are in addition to the existing:

- `temstapro_bin`

## Runtime Behavior

### Current behavior to remove

The runner currently calls TemStaPro with:

- a configured `temstapro_bin`
- a hardcoded `model_dir`
- a hardcoded `cache_dir`
- no explicit Conda runtime wrapper
- no explicit TemStaPro working directory
- no explicit `HF_HOME`
- no explicit `TRANSFORMERS_OFFLINE`

### New behavior

The TemStaPro stage should run with a command shape equivalent to:

```bash
<conda_bin> run -n <temstapro_conda_env_name> <temstapro_bin> \
  -f <input_faa> \
  -d <temstapro_model_dir> \
  -e <temstapro_cache_dir> \
  --mean-output <output_tsv>
```

The subprocess invocation should also use:

- `cwd=<temstapro_repo_root>`
- environment overlay:
  - `HF_HOME=<temstapro_hf_home>`
  - `TRANSFORMERS_OFFLINE=1` when `temstapro_transformers_offline` is true

The stage must still preserve existing output behavior:

- `temstapro_raw.tsv`
- downstream parsing
- `scores.tsv`
- `DONE.json`

## Code Changes

### `src/thermo_mining/settings.py`

Extend `ToolSettings` and `load_settings()` to support:

- `conda_bin`
- `temstapro_conda_env_name`
- `temstapro_repo_root`
- `temstapro_model_dir`
- `temstapro_cache_dir`
- `temstapro_hf_home`
- `temstapro_transformers_offline`

Environment variable support should follow the existing pattern. Recommended
names:

- `THERMO_CONDA_BIN`
- `THERMO_TEMSTAPRO_CONDA_ENV_NAME`
- `THERMO_TEMSTAPRO_REPO_ROOT`
- `THERMO_TEMSTAPRO_MODEL_DIR`
- `THERMO_TEMSTAPRO_CACHE_DIR`
- `THERMO_TEMSTAPRO_HF_HOME`
- `THERMO_TEMSTAPRO_TRANSFORMERS_OFFLINE`

### `config/platform.example.yaml`

Add example values for the new fields with generic Linux-style placeholders.

### `config/platform.server.ubuntu.yaml`

Populate the new fields with the actual server values already established:

- `conda_bin: /mnt/disk3/tio_nekton4/miniconda3/bin/conda`
- `temstapro_conda_env_name: temstapro_env_CPU`
- `temstapro_repo_root: /mnt/disk3/tio_nekton4/TemStaPro-main`
- `temstapro_model_dir: /mnt/disk3/tio_nekton4/TemStaPro-main/models`
- `temstapro_cache_dir: /mnt/disk3/tio_nekton4/TemStaPro-main/cache`
- `temstapro_hf_home: /mnt/disk3/tio_nekton4/.cache/huggingface`
- `temstapro_transformers_offline: true`

### `src/thermo_mining/steps/temstapro_screen.py`

Refactor TemStaPro command building to support:

- `conda_bin`
- `conda_env_name`
- `repo_root`
- `model_dir`
- `cache_dir`
- `hf_home`
- `transformers_offline`

Do not require callers to pre-activate a shell environment.

### `src/thermo_mining/control_plane/runner.py`

Replace hardcoded TemStaPro values with `settings.tools.*` values and pass them
through to the TemStaPro stage runner.

## Testing Strategy

### Settings tests

Add coverage proving the new settings fields load correctly from YAML and env
overrides.

### TemStaPro command tests

Add coverage proving the TemStaPro command now begins with:

- `<conda_bin>`
- `run`
- `-n`
- `<temstapro_conda_env_name>`

and still includes:

- `-f`
- `-d`
- `-e`
- `--mean-output`

### Subprocess invocation tests

Add coverage proving TemStaPro stage execution passes:

- `cwd=<temstapro_repo_root>`
- `HF_HOME`
- `TRANSFORMERS_OFFLINE`

### Runner integration tests

Add coverage proving the control-plane runner passes the configured TemStaPro
runtime values instead of hardcoded defaults.

## Success Criteria

This change is successful when:

- there are no hardcoded TemStaPro model/cache paths left in the control-plane
  runtime path
- the TemStaPro stage can be fully parameterized from platform config
- the runtime no longer depends on manual `conda activate`
- the new server config file can express the real TemStaPro deployment layout
- tests prove command construction, environment injection, and runner wiring
- this change does not alter Foldseek or ProTrek behavior

## Follow-Up Work

After this TemStaPro-specific blocker is closed, the remaining server-completion
work is still at least:

- Foldseek local-binary support or HTTP service setup
- ProTrek weights-file versus weights-directory contract cleanup
- final runtime root decisions (`inputs`, `runs`, `logs`) if repo-local defaults
  are not desired
