import pytest

from thermo_mining.control_plane.planner import apply_review_edits, plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order
from thermo_mining.control_plane.status_explainer import explain_failure


class FakeLLMClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def plan(self, **_: object) -> dict[str, object]:
        return self.payload


def test_plan_from_message_uses_valid_llm_payload():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    payload = {
        "assistant_message": "Planned the proteins flow",
        "execution_plan": {
            "bundle_type": "proteins",
            "input_items": [bundle.model_dump()],
            "stage_order": ["prefilter", "mmseqs_cluster"],
            "parameter_overrides": {},
            "output_root": "/runs/S01",
            "resume_policy": "if_possible",
            "requires_confirmation": True,
            "explanation": "Use the proteins-only path",
        },
        "plan_warnings": [],
    }

    result = plan_from_message("run the proteins file", [bundle], client=FakeLLMClient(payload))

    assert result["assistant_message"] == "Planned the proteins flow"
    assert result["execution_plan"].bundle_type == "proteins"


def test_plan_from_message_falls_back_when_llm_payload_is_invalid():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )

    result = plan_from_message("run default proteins pipeline", [bundle], client=FakeLLMClient({"oops": "bad"}))

    assert result["execution_plan"].bundle_type == "proteins"
    assert result["plan_warnings"]


def test_explain_failure_mentions_stage_and_error_summary():
    text = explain_failure({"active_stage": "mmseqs_cluster", "error_summary": "mmseqs exited with code 1"})

    assert "mmseqs_cluster" in text
    assert "code 1" in text


def test_apply_review_edits_rejects_non_editable_fields():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    plan = ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="planned",
    )

    with pytest.raises(ValueError):
        apply_review_edits(plan, {"stage_order": ["bad"]})
