import importlib
import sys
import types

import pytest

from thermo_mining.control_plane.planner import apply_review_edits, plan_from_message
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order
from thermo_mining.control_plane.status_explainer import explain_failure, explain_run_status


class FakeLLMClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def plan(self, **_: object) -> dict[str, object]:
        self.calls.append(_)
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
            "stage_order": build_stage_order("proteins"),
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


def test_plan_from_message_includes_bundle_context_in_prompt():
    bundles = [
        InputBundle(
            bundle_type="proteins",
            sample_id="S01",
            input_paths=["/mnt/disk2/S01.faa"],
            metadata={},
            output_root="/runs/S01",
        ),
        InputBundle(
            bundle_type="contigs",
            sample_id="S02",
            input_paths=["/mnt/disk2/S02_contigs.fa"],
            metadata={},
            output_root="/runs/S02",
        ),
    ]
    client = FakeLLMClient(
        {
            "assistant_message": "Planned the proteins flow",
            "execution_plan": {
                "bundle_type": "proteins",
                "input_items": [bundles[0].model_dump()],
                "stage_order": build_stage_order("proteins"),
                "parameter_overrides": {},
                "output_root": "/runs/S01",
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "Use the proteins-only path",
            },
            "plan_warnings": [],
        }
    )

    plan_from_message("run the proteins file", bundles, client=client)

    assert client.calls
    assert "bundle_type: proteins" in client.calls[0]["user_prompt"]
    assert "sample_id: S01" in client.calls[0]["user_prompt"]
    assert "/mnt/disk2/S01.faa" in client.calls[0]["user_prompt"]
    assert "output_root: /runs/S01" in client.calls[0]["user_prompt"]


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


def test_plan_from_message_falls_back_when_llm_stage_order_is_invalid():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    client = FakeLLMClient(
        {
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
    )

    result = plan_from_message("run the proteins file", [bundle], client=client)

    assert result["execution_plan"].stage_order == build_stage_order("proteins")
    assert result["plan_warnings"]


def test_plan_from_message_falls_back_when_llm_uses_unknown_inputs():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )
    client = FakeLLMClient(
        {
            "assistant_message": "Planned the proteins flow",
            "execution_plan": {
                "bundle_type": "proteins",
                "input_items": [
                    {
                        "bundle_type": "proteins",
                        "sample_id": "invented",
                        "input_paths": ["/mnt/disk2/ghost.faa"],
                        "metadata": {},
                        "output_root": "/runs/ghost",
                    }
                ],
                "stage_order": build_stage_order("proteins"),
                "parameter_overrides": {},
                "output_root": "/runs/S01",
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "Use the proteins-only path",
            },
            "plan_warnings": [],
        }
    )

    result = plan_from_message("run the proteins file", [bundle], client=client)

    assert result["execution_plan"].input_items == [bundle]
    assert result["plan_warnings"]


def test_explain_failure_mentions_stage_and_error_summary():
    text = explain_failure({"active_stage": "mmseqs_cluster", "error_summary": "mmseqs exited with code 1"})

    assert "mmseqs_cluster" in text
    assert "code 1" in text


def test_explain_run_status_mentions_status_and_stage():
    text = explain_run_status({"status": "running", "active_stage": "prefilter"})

    assert "running" in text
    assert "prefilter" in text


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


def test_apply_review_edits_merges_editable_fields():
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
        parameter_overrides={"prefilter_min_length": 80},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="planned",
    )

    updated = apply_review_edits(
        plan,
        {
            "output_root": "/runs/S01-revised",
            "resume_policy": "never",
            "thermo_min_score": 0.9,
        },
    )

    assert updated.output_root == "/runs/S01-revised"
    assert updated.resume_policy == "never"
    assert updated.parameter_overrides == {
        "prefilter_min_length": 80,
        "thermo_min_score": 0.9,
    }


def test_openai_planner_client_plan_uses_responses_api(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type(
                "FakeResponse",
                (),
                {
                    "output": [
                        type(
                            "FakeOutput",
                            (),
                            {"content": [type("FakeContent", (), {"json": {"assistant_message": "ok"}})()]},
                        )()
                    ]
                },
            )()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_init"] = kwargs
            self.responses = FakeResponses()

    fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)
    sys.modules.pop("thermo_mining.control_plane.llm_client", None)
    llm_client = importlib.import_module("thermo_mining.control_plane.llm_client")

    client = llm_client.OpenAIPlannerClient(model="gpt-test", api_key="secret", base_url="http://localhost")
    result = client.plan(system_prompt="system", user_prompt="user")

    assert captured["client_init"] == {"api_key": "secret", "base_url": "http://localhost"}
    assert captured["model"] == "gpt-test"
    assert captured["input"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]
    assert result == {"assistant_message": "ok"}
