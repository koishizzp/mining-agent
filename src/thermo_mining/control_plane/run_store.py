from contextlib import contextmanager
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .schemas import ArtifactEntry, ExecutionPlan, RunRecord


class ActiveRunConflictError(RuntimeError):
    pass


def _control_dir(runs_root: str | Path) -> Path:
    return Path(runs_root) / "_control_plane"


def _active_marker_path(runs_root: str | Path) -> Path:
    return _control_dir(runs_root) / "active_run.json"


def _active_lock_path(runs_root: str | Path) -> Path:
    return _control_dir(runs_root) / "active_run.lock"


@contextmanager
def _active_run_lock(runs_root: str | Path, timeout_seconds: float = 2.0):
    lock_path = _active_lock_path(runs_root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with lock_path.open("x", encoding="utf-8"):
                break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for active-run lock: {lock_path}")
            time.sleep(0.01)
    try:
        yield
    finally:
        if lock_path.exists():
            lock_path.unlink()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_active_run_unlocked(runs_root: str | Path) -> str | None:
    marker = _active_marker_path(runs_root)
    if not marker.exists():
        return None
    return json.loads(marker.read_text(encoding="utf-8"))["run_id"]


def _set_active_run_unlocked(runs_root: str | Path, run_id: str) -> None:
    control_dir = _control_dir(runs_root)
    control_dir.mkdir(parents=True, exist_ok=True)
    _active_marker_path(runs_root).write_text(
        json.dumps({"run_id": run_id}),
        encoding="utf-8",
    )


def _clear_active_run_unlocked(runs_root: str | Path) -> None:
    marker = _active_marker_path(runs_root)
    if marker.exists():
        marker.unlink()


def create_pending_run(runs_root: str | Path, plan: ExecutionPlan) -> RunRecord:
    runs_root = Path(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)

    run_id = f"run_{uuid4().hex[:8]}"
    run_dir = runs_root / run_id
    (run_dir / "stage_logs").mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    (run_dir / "reports").mkdir()

    record = RunRecord(
        run_id=run_id,
        status="pending",
        created_at=_now_iso(),
        run_dir=str(run_dir),
    )

    (run_dir / "execution_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "bundle_manifest.json").write_text(
        json.dumps([item.model_dump() for item in plan.input_items], indent=2),
        encoding="utf-8",
    )
    write_runtime_state(
        run_dir,
        {
            "run_id": run_id,
            "status": "pending",
            "active_stage": None,
            "stages": [],
        },
    )
    return record


def write_runtime_state(run_dir: str | Path, payload: dict[str, object]) -> None:
    Path(run_dir, "runtime_state.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def read_runtime_state(run_dir: str | Path) -> RunRecord:
    payload = json.loads(Path(run_dir, "runtime_state.json").read_text(encoding="utf-8"))
    return RunRecord(
        run_id=payload["run_id"],
        status=payload["status"],
        created_at=payload.get("created_at", ""),
        confirmed_at=payload.get("confirmed_at"),
        tmux_session=payload.get("tmux_session"),
        run_dir=str(Path(run_dir)),
    )


def set_active_run(runs_root: str | Path, run_id: str) -> None:
    with _active_run_lock(runs_root):
        _set_active_run_unlocked(runs_root, run_id)


def read_active_run(runs_root: str | Path) -> str | None:
    return _read_active_run_unlocked(runs_root)


def clear_active_run(runs_root: str | Path) -> None:
    with _active_run_lock(runs_root):
        _clear_active_run_unlocked(runs_root)


def claim_active_run(runs_root: str | Path, run_id: str) -> bool:
    with _active_run_lock(runs_root):
        active = _read_active_run_unlocked(runs_root)
        if active is None:
            _set_active_run_unlocked(runs_root, run_id)
            return True
        if active == run_id:
            return False
        raise ActiveRunConflictError(f"active run already exists: {active}")


def clear_active_run_if_match(runs_root: str | Path, run_id: str) -> bool:
    with _active_run_lock(runs_root):
        active = _read_active_run_unlocked(runs_root)
        if active != run_id:
            return False
        _clear_active_run_unlocked(runs_root)
        return True


def list_artifacts(run_dir: str | Path) -> list[ArtifactEntry]:
    base = Path(run_dir)
    roots = [base / "artifacts", base / "reports"]
    rows: list[ArtifactEntry] = []

    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                stat = path.stat()
                rows.append(
                    ArtifactEntry(
                        kind=path.suffix.lstrip(".") or "file",
                        path=str(path),
                        label=path.name,
                        size=stat.st_size,
                        updated_at=stat.st_mtime,
                    )
                )
    return rows
