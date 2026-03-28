import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .schemas import ArtifactEntry, ExecutionPlan, RunRecord


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    control_dir = Path(runs_root) / "_control_plane"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "active_run.json").write_text(
        json.dumps({"run_id": run_id}),
        encoding="utf-8",
    )


def read_active_run(runs_root: str | Path) -> str | None:
    marker = Path(runs_root) / "_control_plane" / "active_run.json"
    if not marker.exists():
        return None
    return json.loads(marker.read_text(encoding="utf-8"))["run_id"]


def clear_active_run(runs_root: str | Path) -> None:
    marker = Path(runs_root) / "_control_plane" / "active_run.json"
    if marker.exists():
        marker.unlink()


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
