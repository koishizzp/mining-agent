# Thermo Mining Server Probe Conda Support Design

## Goal

Extend the existing standalone server probe so it can understand Conda-backed
tool locations without requiring the user to activate an environment first.
The probe must support both an explicit Conda prefix and a Conda environment
name, while still preserving the probe's core rule: report facts and fallback
behavior clearly instead of pretending uncertain values are final.

## Relationship To Existing Probe

This design is an extension of:

- `docs/superpowers/specs/2026-03-30-thermo-mining-server-probe-design.md`

That original spec remains valid. This new spec narrows one specific gap:
some required binaries may only exist inside a Conda environment. The current
probe can only find them if the user happens to run the probe inside an
already-activated environment. This extension removes that limitation by
teaching the probe how to resolve and inspect a target Conda environment
explicitly.

## Scope

### In scope

- Add support for `--conda-prefix`
- Add support for `--conda-name`
- Add fallback use of the currently active Conda environment when no explicit
  Conda target is passed
- Record Conda resolution metadata in `server_probe.json`
- Record whether each detected tool came from Conda or from a non-Conda source
- Add warnings when a Conda target resolves successfully but a tool is only
  found outside that environment

### Out of scope

- Enumerating all Conda environments and guessing the best one
- Auto-running `conda activate`
- Modifying the caller's shell environment
- Making Conda mandatory
- Adding a `conda:` section to `platform.server-draft.yaml`

## Locked Decisions

- Both `--conda-prefix` and `--conda-name` are supported
- Resolution priority is fixed:
  1. explicit `--conda-prefix`
  2. explicit `--conda-name`
  3. currently active Conda environment
  4. existing non-Conda probe behavior
- `--conda-name` resolves through `conda env list --json`
- If Conda resolution fails, the probe falls back to existing non-Conda
  detection instead of aborting
- When a Conda environment is resolved but a tool is only found outside it,
  the probe accepts that non-Conda result **and** emits a warning

## CLI Changes

The probe adds these optional arguments:

```text
--conda-prefix /absolute/path/to/env
--conda-name env_name
```

Rules:

- both may exist on the CLI, but `--conda-prefix` wins
- if neither is provided, the probe may still use the currently active Conda
  environment if `CONDA_PREFIX` is present
- the probe must not require `conda` to be installed unless `--conda-name`
  needs to be resolved

## Conda Resolution Model

The probe introduces a `conda` section in `server_probe.json`:

```json
{
  "conda": {
    "requested_mode": "none | prefix | name | active_env",
    "requested_name": null,
    "requested_prefix": null,
    "resolved_prefix": null,
    "active_prefix": null,
    "active_env_name": null,
    "status": "detected | missing | manual",
    "notes": []
  }
}
```

### Field meanings

- `requested_mode`
  - `prefix`: user passed `--conda-prefix`
  - `name`: user passed `--conda-name`
  - `active_env`: nothing explicit was passed, but `CONDA_PREFIX` exists
  - `none`: no explicit or active Conda target was available
- `requested_name`
  - the exact `--conda-name` value if provided
- `requested_prefix`
  - the exact `--conda-prefix` value if provided
- `resolved_prefix`
  - the actual Conda environment path the probe will inspect for tools
- `active_prefix`
  - value of `CONDA_PREFIX` if present
- `active_env_name`
  - value of `CONDA_DEFAULT_ENV` if present
- `status`
  - `detected` if a Conda environment was successfully resolved for inspection
  - `missing` if an explicit Conda request could not be resolved
  - `manual` if no Conda target was requested or available
- `notes`
  - human-readable explanation strings for fallback or ambiguity

## Tool Metadata Changes

Each entry in `tools` adds:

- `source`
- `from_conda`

Allowed `source` values:

- `conda_prefix`
- `active_conda_env`
- `path`
- `candidate_path`
- `missing`

`from_conda` is:

- `true` when the detected tool path came from the resolved Conda environment
- `false` otherwise

Example:

```json
{
  "tools": {
    "fastp": {
      "status": "detected",
      "path": "/mnt/disk3/.../envs/thermo/bin/fastp",
      "version_text": "fastp 0.23.4",
      "source": "conda_prefix",
      "from_conda": true
    }
  }
}
```

## YAML And TXT Output Changes

### `platform.server-draft.yaml`

No new top-level `conda:` section is added. The current runtime config does not
consume Conda metadata directly. YAML continues to only express effective
configuration values such as:

- `tools.fastp_bin`
- `tools.mmseqs_bin`
- `tools.protrek_python_bin`

The Conda-specific resolution details stay in `server_probe.json`.

### `server_probe.txt`

The human summary adds short Conda lines such as:

- `conda request: name thermo`
- `conda resolved prefix: /mnt/disk3/.../envs/thermo`
- `fastp source: conda_prefix`
- `tmux source: path`

## Resolution Algorithm

### 1. Explicit `--conda-prefix`

If provided:

- treat the argument as the requested Conda environment path
- if the directory exists, set:
  - `requested_mode = "prefix"`
  - `status = "detected"`
  - `resolved_prefix = <that path>`
- if the directory does not exist, set:
  - `requested_mode = "prefix"`
  - `status = "missing"`
  - add a warning
  - continue with non-Conda fallback behavior

### 2. Explicit `--conda-name`

If `--conda-prefix` is absent and `--conda-name` is present:

- run `conda env list --json`
- parse the list of environment prefixes
- resolve the requested name by matching the final path segment or the named
  environment entry
- if resolved:
  - `requested_mode = "name"`
  - `status = "detected"`
  - `resolved_prefix = <matched prefix>`
- if `conda` command is unavailable:
  - `requested_mode = "name"`
  - `status = "missing"`
  - add a warning
  - continue with non-Conda fallback behavior
- if the name is not found:
  - `requested_mode = "name"`
  - `status = "missing"`
  - add a warning
  - continue with non-Conda fallback behavior

### 3. Currently active Conda environment

If no explicit Conda target is provided:

- read `CONDA_PREFIX`
- read `CONDA_DEFAULT_ENV`
- if `CONDA_PREFIX` exists:
  - `requested_mode = "active_env"`
  - `status = "detected"`
  - `resolved_prefix = CONDA_PREFIX`
- otherwise:
  - `requested_mode = "none"`
  - `status = "manual"`

### 4. Non-Conda fallback

If no Conda environment is resolved, or if individual tools are missing from
the resolved environment:

- fall back to the existing logic:
  - deterministic `shutil.which(...)`
  - existing candidate-path logic where applicable

## Tool Detection Order

For tool binaries such as:

- `tmux`
- `fastp`
- `spades.py`
- `prodigal`
- `mmseqs`
- `temstapro`

the detection order becomes:

1. check `<resolved_conda_prefix>/bin/<tool>` when a Conda target is resolved
2. if not found there, use existing `shutil.which(...)`
3. record which source actually won

The probe does not require that every tool come from Conda. Some tools may
still reasonably come from the normal system `PATH`.

## Warning Behavior

When a Conda target resolves successfully but a tool is only found outside that
environment:

- accept the non-Conda path
- set `source` appropriately (`path` or `candidate_path`)
- set `from_conda = false`
- add a warning explaining that the tool was not found inside the requested or
  active Conda environment

This keeps the probe practical without hiding environment drift.

## Failure Semantics

The probe still distinguishes environment incompleteness from probe failure.

Examples:

- explicit `--conda-prefix` does not exist
  - warning
  - `conda.status = "missing"`
  - continue
- explicit `--conda-name` cannot be resolved
  - warning
  - `conda.status = "missing"`
  - continue
- `conda` command is unavailable
  - warning if `--conda-name` was requested
  - continue

As before, if the probe still writes its output files successfully, exit code is
`0`.

## Success Criteria

This extension is successful when:

- the probe supports both `--conda-prefix` and `--conda-name`
- explicit Conda prefix takes precedence over Conda name
- Conda name resolution uses `conda env list --json`
- the currently active Conda environment is used when no explicit Conda target
  is passed
- tool entries clearly record whether they came from Conda
- the JSON report clearly records Conda request and resolution metadata
- YAML remains compatible with the existing platform config shape
- the probe still falls back gracefully when Conda resolution fails
- warnings make mixed Conda/non-Conda tool sourcing visible instead of silent

## Non-Goals For This Extension

This extension still does not cover:

- auto-activating a shell environment
- editing `.bashrc`, `.zshrc`, or Conda initialization
- scanning every Conda environment on the machine
- automatically choosing the "best" Conda environment
