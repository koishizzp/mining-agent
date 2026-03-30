# Thermo Mining Server Probe Design

## Goal

Add a server-side probe utility that can run **before this repository is cloned**
to a target Linux server and produce low-ambiguity environment artifacts for
later deployment work. The probe is not a deployment script. Its job is to tell
us what already exists on the server, what is missing, and which configuration
values must still be chosen manually.

The primary success condition is not "the server is ready." The success
condition is "the next agent can read the probe output and continue the server
adaptation work without guessing."

## Context

The current control-plane implementation expects a configuration shape matching
`config/platform.example.yaml` and `src/thermo_mining/settings.py`. That means
deployment work eventually needs concrete values for:

- repository and config paths
- tool binaries
- ProTrek-related paths
- runtime directories
- service host and port
- Foldseek service URL

At the moment, the repository has **not** been cloned to the server. That makes
some fields discoverable now and other fields impossible to discover honestly.
The probe must preserve that distinction instead of fabricating final values.

## Scope

### In scope

- A single Python 3 probe script that runs on the target Linux server
- No dependency on this repository being present on the server
- Standard-library-only implementation
- Structured output for agent consumption
- Human-readable summary output
- A draft `platform.yaml` matching the current repo config shape
- Explicit status labeling for each probed item

### Out of scope

- Cloning the repository
- Installing missing tools
- Editing system configuration
- Starting or stopping services
- Declaring the server fully deployment-ready
- Guessing final repository paths or service topology

## Locked Decisions

- The script is **server-specific**, not a portability layer
- The script is implemented in `python3`, not pure shell
- Output is **structure-first**:
  - `JSON` is the canonical machine-readable artifact
  - `YAML` is a draft config derived from probe results
  - `TXT` is a compact human summary
- The script must work **before** repo clone
- The script must never promote uncertain values to "final"

## Primary Output Contract

The probe writes into an output directory, defaulting to:

```text
./thermo_server_probe
```

It creates exactly these files:

```text
thermo_server_probe/
  server_probe.json
  platform.server-draft.yaml
  server_probe.txt
```

### Canonical artifact: `server_probe.json`

This file is the primary handoff artifact for later agent work. It must contain
enough structured data that a later agent can continue environment adaptation
without reparsing free-form shell output.

Required top-level structure:

```json
{
  "metadata": {},
  "deployment": {},
  "tools": {},
  "protrek": {},
  "foldseek": {},
  "runtime": {},
  "service": {},
  "warnings": []
}
```

Each probe item records a `status` value from this closed set:

- `detected`
  - the script confirmed the value exists and can name it directly
- `missing`
  - the script searched its allowed locations and did not find a usable value
- `candidate`
  - the value is plausible but should still be reviewed before being treated as
    final
- `manual`
  - the value cannot be discovered honestly at this stage and must be filled in
    by a human later

### Draft config artifact: `platform.server-draft.yaml`

This file mirrors the existing runtime config structure used by the repo:

- `llm`
- `runtime`
- `service`
- `logging`
- `tools`
- `defaults`

The probe fills in:

- values that are truly detected
- values that are only recommendations when that is honest
- explicit placeholders for fields that still require manual choice

Examples of acceptable placeholder values:

```yaml
tools:
  foldseek_base_url: "__MANUAL__: set Foldseek service URL"
```

```yaml
runtime:
  runs_root: "__MANUAL__: choose final runs directory"
```

The draft YAML is for later completion, not for immediate blind use.

Deployment metadata such as `repo_root` and `config_path` remain in
`server_probe.json` and `server_probe.txt`; they are not injected as extra
top-level keys into the draft YAML because the current repo config does not use
such keys.

### Human summary artifact: `server_probe.txt`

This file is a concise summary for manual inspection. It is secondary and not
the canonical artifact for later automation.

## Data Model

### `metadata`

Must include:

- `hostname`
- `user`
- `cwd`
- `generated_at`
- `python3_path`
- `python3_version`
- `platform`

### `deployment`

Must include:

- `repo_root`
- `config_path`

Both are `manual` in the initial probe because the repository has not been
cloned yet.

### `tools`

Must include entries for:

- `tmux`
- `fastp`
- `spades_py`
- `prodigal`
- `mmseqs`
- `temstapro`

Each tool entry records:

- `status`
- `path`
- `version_text`
- optional `notes`

### `protrek`

Must include:

- `python_bin`
- `repo_root`
- `weights_dir`

Each entry records:

- `status`
- `path`
- optional `notes`

### `foldseek`

Must include:

- `base_url`
- `connectivity`
- optional `notes`

The `base_url` is `manual` unless there is a strong, local candidate.

### `runtime`

Must include:

- `data_root`
- `runs_root`
- `log_path`

These may be `candidate` or `manual` depending on what the script can support
honestly.

### `service`

Must include:

- `host`
- `port`

These may be recommended defaults instead of machine-detected facts.

### `warnings`

This array holds issues such as:

- missing tools
- multiple plausible ProTrek roots
- runtime roots that need manual review
- foldseek URL still unresolved

## Detection Strategy

The probe uses two different strategies depending on the type of value.

### 1. Deterministic detection

Used when the server can answer the question directly and safely.

Targets:

- `python3`
- `tmux`
- `fastp`
- `spades.py`
- `prodigal`
- `mmseqs`
- `temstapro`

Mechanisms:

- `sys.executable` and `python3 --version`
- `shutil.which(...)`
- short version probes such as:
  - `--version`
  - fallback to `-v`
  - fallback to `version`

Version capture is best-effort. Failure to obtain a version string must not
convert a detected binary into a missing one.

### 2. Candidate detection

Used when a value may exist but cannot be declared final without human review.

Targets:

- ProTrek python
- ProTrek repo root
- ProTrek weights directory
- runtime roots
- Foldseek local URL candidate

Candidate detection is intentionally narrow. The script does **not** scan the
entire filesystem.

#### ProTrek candidate roots

The probe checks a bounded list such as:

- `/srv/ProTrek`
- `/opt/ProTrek`
- `/mnt/disk1/ProTrek`
- `/mnt/disk2/ProTrek`
- `/mnt/disk3/ProTrek`
- `/mnt/disk4/ProTrek`

Candidate `python_bin` locations may include:

- `/opt/protrek/bin/python`
- `/srv/ProTrek/.venv/bin/python`
- `/usr/bin/python3`

Weights candidates are checked only relative to discovered candidate roots and
common weight subdirectories. The probe does not recursively crawl disks.

#### Runtime directory candidates

The probe may inspect a short list of likely storage roots:

- `/mnt/disk1`
- `/mnt/disk2`
- `/mnt/disk3`
- `/mnt/disk4`
- the current user's home directory

It may recommend candidate values like:

- `data_root`: a likely input-oriented location
- `runs_root`: a likely large-output location
- `log_path`: `<runs_root>/platform.log`

These remain `candidate` unless there is an explicit reason they are clearly
the intended deployment directories.

#### Foldseek candidate URL

The probe may check whether a local default candidate responds:

- `http://127.0.0.1:8100`

If the endpoint appears reachable, the result may be recorded as `candidate`.
If not, the value remains `manual`.

The probe must not guess arbitrary remote hosts or ports.

## Manual-Only Fields

The first probe must **never** claim final values for:

- `deployment.repo_root`
- `deployment.config_path`
- `foldseek.base_url` when no trusted local candidate is available

These values depend on future deployment decisions rather than current machine
facts.

## Default Recommendations

Some settings may be emitted as explicit recommendations rather than detections:

- `service.host`
  - default recommendation: `127.0.0.1`
- `service.port`
  - default recommendation: `8000`

These are configuration defaults for the first server deployment, not discovered
facts about the machine.

## Safety Rules

The probe must not:

- modify system state outside its output directory
- install packages
- clone repositories
- start or stop services
- recursively scan the entire filesystem
- silently convert uncertainty into certainty
- hide missing dependencies by writing fake paths

The only writes allowed are the output artifacts under the chosen output
directory.

## Error Handling

The probe is resilient to partial failure.

Rules:

- one missing tool must not abort the whole probe
- one failed version check must not abort the whole probe
- the script returns exit code `0` if it successfully writes all output files,
  even if many probe items are `missing` or `manual`
- the script returns non-zero only when the probe itself fails, such as:
  - cannot create the output directory
  - cannot serialize the output artifacts
  - uncaught internal error

This keeps "the environment is incomplete" separate from "the probe failed."

## Human Workflow

1. Copy the standalone probe script to the target Linux server
2. Run it with `python3`
3. Collect:
   - `server_probe.json`
   - `platform.server-draft.yaml`
   - `server_probe.txt`
4. Feed those artifacts back into the repo workflow
5. Use them to finish server-specific configuration and deployment decisions

## Success Criteria

The design is successful when the implemented probe:

- runs on the target Linux server with only `python3`
- does not require the repository to already exist on that server
- produces the three agreed output files
- records discovered values in a machine-readable structure
- clearly marks `detected`, `missing`, `candidate`, and `manual` values
- emits a draft YAML compatible with the current repo configuration shape
- does not fabricate final values for repo path, config path, or unresolved
  Foldseek service URL
- gives a later agent enough structured information to continue server
  adaptation without guessing

## Non-Goals For This Spec

This spec intentionally stops at the probe utility. It does not cover:

- automatic installation of missing dependencies
- automatic generation of a production-ready final config
- Linux service management
- repository sync strategy
- ongoing health monitoring
