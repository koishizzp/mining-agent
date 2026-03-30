def explain_failure(runtime_state: dict[str, object]) -> str:
    stage = runtime_state.get("active_stage") or "unknown stage"
    summary = runtime_state.get("error_summary") or "no error summary was recorded"
    return f"The run failed during {stage}. Latest summary: {summary}."


def explain_run_status(runtime_state: dict[str, object]) -> str:
    status = runtime_state.get("status", "unknown")
    stage = runtime_state.get("active_stage") or "idle"
    return f"The run is currently {status}. Active stage: {stage}."
