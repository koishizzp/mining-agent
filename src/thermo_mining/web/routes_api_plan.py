from fastapi import APIRouter

from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.web.dependencies import get_llm_client

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan")
def create_plan(payload: dict[str, object]) -> dict[str, object]:
    bundles = [InputBundle.model_validate(row) for row in payload["selected_bundles"]]
    planned = plan_from_message(str(payload["message"]), bundles, client=get_llm_client())
    execution_plan = planned["execution_plan"]
    if isinstance(execution_plan, dict):
        execution_plan = ExecutionPlan.model_validate(execution_plan)
    return {
        "assistant_message": planned["assistant_message"],
        "execution_plan": execution_plan.model_dump(),
        "plan_warnings": planned["plan_warnings"],
    }
