from fastapi import APIRouter, HTTPException

from thermo_mining.control_plane.planner import apply_review_edits
from thermo_mining.control_plane.run_store import create_pending_run, list_artifacts, read_active_run
from thermo_mining.control_plane.schemas import ExecutionPlan
from thermo_mining.web.dependencies import get_job_manager, get_settings

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
def create_run(payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    if read_active_run(settings.runtime.runs_root):
        raise HTTPException(status_code=409, detail="an active run already exists")

    execution_plan_payload = payload["execution_plan"] if "execution_plan" in payload else payload
    base_plan = ExecutionPlan.model_validate(execution_plan_payload)
    plan = apply_review_edits(base_plan, payload.get("review_edits", {}))
    record = create_pending_run(settings.runtime.runs_root, plan)
    return {"run_id": record.run_id}


@router.post("/{run_id}/confirm")
def confirm_run(run_id: str) -> dict[str, object]:
    session_name = get_job_manager().confirm_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.post("/{run_id}/stop")
def stop_run(run_id: str) -> dict[str, object]:
    get_job_manager().stop_run(run_id)
    return {"run_id": run_id, "status": "stopped"}


@router.post("/{run_id}/terminate")
def terminate_run(run_id: str) -> dict[str, object]:
    get_job_manager().terminate_run(run_id)
    return {"run_id": run_id, "status": "failed"}


@router.post("/{run_id}/resume")
def resume_run(run_id: str) -> dict[str, object]:
    session_name = get_job_manager().resume_run(run_id)
    return {"run_id": run_id, "tmux_session": session_name}


@router.get("/active")
def get_active_run() -> dict[str, object]:
    return {"run_id": read_active_run(get_settings().runtime.runs_root)}


@router.get("/{run_id}")
def get_run_detail(run_id: str) -> dict[str, object]:
    return {"run_id": run_id}


@router.get("/{run_id}/logs")
def get_run_logs(run_id: str) -> dict[str, object]:
    return {"run_id": run_id, "lines": []}


@router.get("/{run_id}/artifacts")
def get_run_artifacts(run_id: str) -> list[dict[str, object]]:
    run_dir = get_settings().runtime.runs_root / run_id
    return [row.model_dump() for row in list_artifacts(run_dir)]
