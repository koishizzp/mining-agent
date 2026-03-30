from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from thermo_mining.control_plane.llm_client import OpenAIPlannerClient
from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.run_store import read_active_run
from thermo_mining.control_plane.schemas import InputBundle
from thermo_mining.control_plane.status_explainer import explain_failure, explain_run_status
from thermo_mining.settings import PlatformSettings
from thermo_mining.web.dependencies import get_llm_client, get_settings

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    selected_bundles: list[InputBundle] | None = None
    runtime_state: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_planning_messages(self) -> "ChatCompletionsRequest":
        if self.selected_bundles and not self.messages:
            raise ValueError("messages must contain at least one item when selected_bundles are provided")
        return self


@router.post("/v1/chat/completions")
def chat_completions(
    payload: ChatCompletionsRequest,
    settings: Annotated[PlatformSettings, Depends(get_settings)],
    llm_client: Annotated[OpenAIPlannerClient, Depends(get_llm_client)],
) -> dict[str, object]:
    active_run = read_active_run(settings.runtime.runs_root)

    if payload.selected_bundles:
        planned = plan_from_message(
            payload.messages[-1].content,
            payload.selected_bundles,
            client=llm_client,
        )
        content = planned["assistant_message"]
    elif payload.runtime_state is not None:
        if payload.runtime_state.get("status") == "failed":
            content = explain_failure(payload.runtime_state)
        else:
            content = explain_run_status(payload.runtime_state)
    elif active_run is None:
        content = explain_run_status({"status": "idle", "active_stage": None})
    else:
        content = explain_run_status({"status": "running", "active_stage": "unknown"})

    return {
        "id": "chatcmpl-control-plane",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
