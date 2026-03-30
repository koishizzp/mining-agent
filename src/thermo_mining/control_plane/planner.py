from .schemas import ExecutionPlan, InputBundle, REVIEW_EDITABLE_FIELDS
from .stage_graph import build_stage_order


def _fallback_plan(message: str, bundles: list[InputBundle], warning: str | None = None) -> dict[str, object]:
    bundle = bundles[0]
    warnings = ["LLM output was invalid; fallback planning was used."]
    if warning is not None:
        warnings.append(warning)
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
        "plan_warnings": warnings,
    }


def _bundle_signature(bundle: InputBundle) -> tuple[str, str, tuple[str, ...], str]:
    return (
        bundle.bundle_type,
        bundle.sample_id,
        tuple(bundle.input_paths),
        bundle.output_root,
    )


def _build_user_prompt(message: str, bundles: list[InputBundle]) -> str:
    lines = [
        "User request:",
        message,
        "",
        "Available input bundles:",
    ]
    for bundle in bundles:
        input_paths = ", ".join(bundle.input_paths)
        lines.extend(
            [
                f"- bundle_type: {bundle.bundle_type}",
                f"  sample_id: {bundle.sample_id}",
                f"  input_paths: {input_paths}",
                f"  output_root: {bundle.output_root}",
            ]
        )
    return "\n".join(lines)


def _validate_plan(plan: ExecutionPlan, bundles: list[InputBundle]) -> None:
    if plan.stage_order != build_stage_order(plan.bundle_type):
        raise ValueError("execution plan stage order does not match the canonical stage graph")
    if len(plan.input_items) != 1:
        raise ValueError("execution plan must currently contain exactly one input item")

    provided_bundles = {_bundle_signature(bundle) for bundle in bundles}
    for bundle in plan.input_items:
        if bundle.bundle_type != plan.bundle_type:
            raise ValueError("execution plan input items must match the selected bundle type")
        if _bundle_signature(bundle) not in provided_bundles:
            raise ValueError("execution plan input items must come from the discovered bundles")


def plan_from_message(message: str, bundles: list[InputBundle], client: object) -> dict[str, object]:
    try:
        payload = client.plan(
            system_prompt=(
                "Return planning JSON with assistant_message, execution_plan, and plan_warnings. "
                "Use only the provided input bundles and the canonical stage order for the selected bundle type."
            ),
            user_prompt=_build_user_prompt(message, bundles),
        )
        execution_plan = ExecutionPlan.model_validate(payload["execution_plan"])
        _validate_plan(execution_plan, bundles)
        return {
            "assistant_message": payload["assistant_message"],
            "execution_plan": execution_plan,
            "plan_warnings": list(payload.get("plan_warnings", [])),
        }
    except Exception as exc:
        return _fallback_plan(message, bundles, warning=str(exc))


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
