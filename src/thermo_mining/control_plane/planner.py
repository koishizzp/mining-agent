from .schemas import ExecutionPlan, InputBundle, REVIEW_EDITABLE_FIELDS
from .stage_graph import build_stage_order


def _fallback_plan(message: str, bundles: list[InputBundle]) -> dict[str, object]:
    bundle = bundles[0]
    return {
        "assistant_message": f"Using the fallback planner for {bundle.bundle_type}",
        "execution_plan": ExecutionPlan(
            bundle_type=bundle.bundle_type,
            input_items=[bundle],
            stage_order=build_stage_order(bundle.bundle_type),
            parameter_overrides={},
            output_root=bundle.output_root,
            resume_policy="if_possible",
            explanation=message,
        ),
        "plan_warnings": ["LLM output was invalid; fallback planning was used."],
    }


def plan_from_message(message: str, bundles: list[InputBundle], client: object) -> dict[str, object]:
    try:
        payload = client.plan(system_prompt="Return valid planning JSON", user_prompt=message)
        return {
            "assistant_message": payload["assistant_message"],
            "execution_plan": ExecutionPlan.model_validate(payload["execution_plan"]),
            "plan_warnings": payload.get("plan_warnings", []),
        }
    except Exception:
        return _fallback_plan(message, bundles)


def apply_review_edits(plan: ExecutionPlan, edits: dict[str, object]) -> ExecutionPlan:
    disallowed = set(edits) - REVIEW_EDITABLE_FIELDS
    if disallowed:
        raise ValueError(f"review edits contain non-editable fields: {sorted(disallowed)}")

    updated_payload = plan.model_dump()
    if "output_root" in edits:
        updated_payload["output_root"] = edits["output_root"]
    if "resume_policy" in edits:
        updated_payload["resume_policy"] = edits["resume_policy"]

    merged_overrides = dict(updated_payload["parameter_overrides"])
    for key, value in edits.items():
        if key not in {"output_root", "resume_policy"}:
            merged_overrides[key] = value
    updated_payload["parameter_overrides"] = merged_overrides
    return ExecutionPlan.model_validate(updated_payload)
