from fastapi import APIRouter

from thermo_mining.control_plane.planner import plan_from_message
from thermo_mining.control_plane.run_store import read_active_run
from thermo_mining.control_plane.schemas import InputBundle
from thermo_mining.control_plane.status_explainer import explain_failure, explain_run_status
from thermo_mining.web.dependencies import get_llm_client, get_settings

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
def chat_completions(payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    active_run = read_active_run(settings.runtime.runs_root)

    if payload.get("selected_bundles"):
        bundles = [InputBundle.model_validate(row) for row in payload["selected_bundles"]]
        planned = plan_from_message(
            str(payload["messages"][-1]["content"]),
            bundles,
            client=get_llm_client(),
        )
        content = planned["assistant_message"]
    elif payload.get("runtime_state", {}).get("status") == "failed":
        content = explain_failure(payload["runtime_state"])
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
