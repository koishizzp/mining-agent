import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from thermo_mining.control_plane.job_manager import JobManager
from thermo_mining.control_plane.planner import apply_review_edits
from thermo_mining.control_plane.run_store import create_pending_run, list_artifacts, read_active_run, read_runtime_state
from thermo_mining.control_plane.schemas import ExecutionPlan
from thermo_mining.settings import PlatformSettings
from thermo_mining.web.dependencies import get_job_manager, get_settings

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_dir(settings: PlatformSettings, run_id: str) -> Path:
    return Path(settings.runtime.runs_root) / run_id


def _require_run_dir(settings: PlatformSettings, run_id: str) -> Path:
    run_dir = _run_dir(settings, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run_dir


def _read_runtime_payload(run_dir: Path) -> dict[str, object]:
    try:
        record = read_runtime_state(run_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"runtime state not found for {run_dir.name}") from exc

    payload = json.loads((run_dir / "runtime_state.json").read_text(encoding="utf-8"))
    payload.setdefault("run_id", record.run_id)
    payload.setdefault("status", record.status)
    payload.setdefault("created_at", record.created_at)
    payload.setdefault("confirmed_at", record.confirmed_at)
    payload.setdefault("tmux_session", record.tmux_session)
    payload.setdefault("run_dir", record.run_dir)
    return payload


@router.post("")
def create_run(
    payload: dict[str, object],
    settings: Annotated[PlatformSettings, Depends(get_settings)],
) -> dict[str, object]:
    if read_active_run(settings.runtime.runs_root):
        raise HTTPException(status_code=409, detail="an active run already exists")

    execution_plan_payload = payload["execution_plan"] if "execution_plan" in payload else payload
    base_plan = ExecutionPlan.model_validate(execution_plan_payload)
    plan = apply_review_edits(base_plan, payload.get("review_edits", {}))
    record = create_pending_run(settings.runtime.runs_root, plan)
    return {"run_id": record.run_id}


@router.post("/{run_id}/confirm")
def confirm_run(
    run_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)],
) -> dict[str, object]:
    session_name = job_manager.confirm_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.post("/{run_id}/stop")
def stop_run(
    run_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)],
) -> dict[str, object]:
    job_manager.stop_run(run_id)
    return {"run_id": run_id, "status": "stopped"}


@router.post("/{run_id}/terminate")
def terminate_run(
    run_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)],
) -> dict[str, object]:
    job_manager.terminate_run(run_id)
    return {"run_id": run_id, "status": "failed"}


@router.post("/{run_id}/resume")
def resume_run(
    run_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)],
) -> dict[str, object]:
    session_name = job_manager.resume_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.get("/active")
def get_active_run(
    settings: Annotated[PlatformSettings, Depends(get_settings)],
) -> dict[str, object]:
    return {"run_id": read_active_run(settings.runtime.runs_root)}


@router.get("/{run_id}")
def get_run_detail(
    run_id: str,
    settings: Annotated[PlatformSettings, Depends(get_settings)],
) -> dict[str, object]:
    return _read_runtime_payload(_require_run_dir(settings, run_id))


@router.get("/{run_id}/logs")
def get_run_logs(
    run_id: str,
    settings: Annotated[PlatformSettings, Depends(get_settings)],
) -> dict[str, object]:
    run_dir = _require_run_dir(settings, run_id)
    stage_logs_dir = run_dir / "stage_logs"
    if not stage_logs_dir.exists():
        return {"run_id": run_id, "lines": []}

    lines: list[str] = []
    for path in sorted(item for item in stage_logs_dir.rglob("*") if item.is_file()):
        lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return {"run_id": run_id, "lines": lines}


@router.get("/{run_id}/artifacts")
def get_run_artifacts(
    run_id: str,
    settings: Annotated[PlatformSettings, Depends(get_settings)],
) -> list[dict[str, object]]:
    run_dir = _require_run_dir(settings, run_id)
    return [row.model_dump() for row in list_artifacts(run_dir)]
