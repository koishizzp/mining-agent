from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from thermo_mining.control_plane.llm_client import OpenAIPlannerClient
from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.web.dependencies import get_llm_client

router = APIRouter(prefix="/api", tags=["plan"])


class PlanRequest(BaseModel):
    message: str
    selected_bundles: list[InputBundle]


@router.post("/plan")
def create_plan(
    payload: PlanRequest,
    llm_client: Annotated[OpenAIPlannerClient, Depends(get_llm_client)],
) -> dict[str, object]:
    planned = plan_from_message(payload.message, payload.selected_bundles, client=llm_client)
    execution_plan = planned["execution_plan"]
    if isinstance(execution_plan, dict):
        execution_plan = ExecutionPlan.model_validate(execution_plan)
    return {
        "assistant_message": planned["assistant_message"],
        "execution_plan": execution_plan.model_dump(),
        "plan_warnings": planned["plan_warnings"],
    }
