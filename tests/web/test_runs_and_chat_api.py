from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app


def test_confirm_run_endpoint_delegates_to_job_manager(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.create_pending_run",
        lambda runs_root, plan: type("Record", (), {"run_id": "run_001"})(),
    )
    monkeypatch.setattr("thermo_mining.web.routes_api_runs.ExecutionPlan.model_validate", lambda payload: payload)
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.get_settings",
        lambda: type("Settings", (), {"runtime": type("Runtime", (), {"runs_root": "/runs"})()})(),
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.get_job_manager",
        lambda: type("Manager", (), {"confirm_run": lambda self, run_id: "thermo_run_001"})(),
    )

    create_response = client.post(
        "/api/runs",
        json={
            "bundle_type": "proteins",
            "input_items": [],
            "stage_order": ["prefilter"],
            "parameter_overrides": {},
            "output_root": "/runs/S01",
            "resume_policy": "if_possible",
            "requires_confirmation": True,
            "explanation": "planned",
        },
    )
    confirm_response = client.post("/api/runs/run_001/confirm")

    assert create_response.status_code == 200
    assert confirm_response.status_code == 200
    assert confirm_response.json()["tmux_session"] == "thermo_run_001"


def test_openai_compatible_chat_returns_message_content(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.explain_run_status",
        lambda runtime_state: "The run is currently idle.",
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.read_active_run",
        lambda runs_root: None,
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.get_settings",
        lambda: type("Settings", (), {"runtime": type("Runtime", (), {"runs_root": "/runs"})()})(),
    )

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "what is the current run status"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "The run is currently idle."
