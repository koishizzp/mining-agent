from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from thermo_mining.control_plane.run_store import create_pending_run, write_runtime_state
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order
from thermo_mining.web.app import create_app
from thermo_mining.web.dependencies import get_job_manager, get_llm_client, get_settings


def _build_plan(output_root: str = "/runs/S01") -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root=output_root,
    )
    return ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root=output_root,
        resume_policy="if_possible",
        explanation="test plan",
    )


def _build_settings(runs_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        llm=SimpleNamespace(model="gpt-4o-mini", api_key="test-key", base_url="https://example.invalid"),
        runtime=SimpleNamespace(runs_root=runs_root),
        tools=SimpleNamespace(tmux_bin="tmux"),
    )


def test_confirm_run_endpoint_delegates_to_job_manager_with_dependency_override(monkeypatch, tmp_path):
    app = create_app()
    client = TestClient(app)
    base_plan = _build_plan()
    updated_plan = _build_plan(output_root="/runs/S02")

    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.ExecutionPlan.model_validate",
        lambda payload: base_plan,
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.apply_review_edits",
        lambda plan, edits: updated_plan if plan is base_plan else (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_runs.create_pending_run",
        lambda runs_root, plan: (
            type("Record", (), {"run_id": "run_001"})() if runs_root == tmp_path and plan is updated_plan else (_ for _ in ()).throw(AssertionError())
        ),
    )

    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)
    app.dependency_overrides[get_job_manager] = lambda: SimpleNamespace(confirm_run=lambda run_id: f"thermo_{run_id}")

    create_response = client.post(
        "/api/runs",
        json=base_plan.model_dump(),
    )
    confirm_response = client.post("/api/runs/run_001/confirm")

    assert create_response.status_code == 200
    assert create_response.json() == {"run_id": "run_001"}
    assert confirm_response.status_code == 200
    assert confirm_response.json()["tmux_session"] == "thermo_run_001"


def test_resume_run_endpoint_uses_dependency_override():
    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_job_manager] = lambda: SimpleNamespace(resume_run=lambda run_id: "thermo_run_001")

    response = client.post("/api/runs/run_001/resume")

    assert response.status_code == 200
    assert response.json() == {"run_id": "run_001", "tmux_session": "thermo_run_001"}


def test_run_detail_endpoint_returns_persisted_runtime_state(tmp_path):
    app = create_app()
    client = TestClient(app)
    record = create_pending_run(tmp_path, _build_plan(output_root=str((tmp_path / "out").resolve())))
    run_dir = Path(record.run_dir)
    write_runtime_state(
        run_dir,
        {
            "run_id": record.run_id,
            "status": "running",
            "created_at": "2026-03-28T00:00:00+00:00",
            "confirmed_at": "2026-03-28T00:05:00+00:00",
            "tmux_session": "thermo_run_001",
            "active_stage": "prefilter",
            "stages": [{"stage_name": "prefilter", "status": "running"}],
        },
    )
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)

    response = client.get(f"/api/runs/{record.run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["active_stage"] == "prefilter"
    assert response.json()["tmux_session"] == "thermo_run_001"


def test_run_logs_endpoint_returns_existing_stage_log_lines(tmp_path):
    app = create_app()
    client = TestClient(app)
    record = create_pending_run(tmp_path, _build_plan(output_root=str((tmp_path / "out").resolve())))
    log_path = Path(record.run_dir) / "stage_logs" / "prefilter.log"
    log_path.write_text("first line\nsecond line\n", encoding="utf-8")
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)

    response = client.get(f"/api/runs/{record.run_id}/logs")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": record.run_id,
        "lines": ["first line", "second line"],
    }


def test_run_detail_and_logs_return_404_for_missing_run(tmp_path):
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)

    detail_response = client.get("/api/runs/run_missing")
    logs_response = client.get("/api/runs/run_missing/logs")

    assert detail_response.status_code == 404
    assert logs_response.status_code == 404


def test_openai_compatible_chat_returns_message_content(monkeypatch, tmp_path):
    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.explain_run_status",
        lambda runtime_state: "The run is currently idle.",
    )

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "what is the current run status"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "The run is currently idle."


def test_openai_compatible_chat_planning_uses_dependency_override(monkeypatch, tmp_path):
    app = create_app()
    client = TestClient(app)
    fake_llm_client = object()
    captured: dict[str, object] = {}
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client

    def fake_plan_from_message(message, bundles, client):
        captured["message"] = message
        captured["bundles"] = bundles
        captured["client"] = client
        return {"assistant_message": "planned", "execution_plan": _build_plan().model_dump(), "plan_warnings": []}

    monkeypatch.setattr("thermo_mining.web.routes_api_chat.plan_from_message", fake_plan_from_message)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "plan this"}],
            "selected_bundles": [
                {
                    "bundle_type": "proteins",
                    "sample_id": "S01",
                    "input_paths": ["/mnt/disk2/S01.faa"],
                    "metadata": {},
                    "output_root": "/runs/S01",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "planned"
    assert captured["message"] == "plan this"
    assert captured["client"] is fake_llm_client
    assert len(captured["bundles"]) == 1


def test_openai_compatible_chat_uses_provided_runtime_state(monkeypatch, tmp_path):
    app = create_app()
    client = TestClient(app)
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)
    monkeypatch.setattr(
        "thermo_mining.web.routes_api_chat.explain_run_status",
        lambda runtime_state: f"{runtime_state['status']}:{runtime_state['active_stage']}",
    )

    response = client.post(
        "/v1/chat/completions",
        json={"runtime_state": {"status": "running", "active_stage": "prefilter"}, "messages": []},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "running:prefilter"


def test_openai_compatible_chat_rejects_malformed_selected_bundles_payload(tmp_path):
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)

    response = client.post(
        "/v1/chat/completions",
        json={
            "selected_bundles": {"bad": "shape"},
            "messages": [{"role": "user", "content": "plan this"}],
        },
    )

    assert response.status_code == 422


def test_openai_compatible_chat_rejects_planning_request_without_messages(tmp_path):
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_settings] = lambda: _build_settings(tmp_path)

    response = client.post(
        "/v1/chat/completions",
        json={
            "selected_bundles": [
                {
                    "bundle_type": "proteins",
                    "sample_id": "S01",
                    "input_paths": ["/mnt/disk2/S01.faa"],
                    "metadata": {},
                    "output_root": "/runs/S01",
                }
            ],
        },
    )

    assert response.status_code == 422
