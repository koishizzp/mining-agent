from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app
from thermo_mining.web.dependencies import get_llm_client


def test_fs_list_endpoint_returns_directory_rows(tmp_path):
    (tmp_path / "sample.faa").write_text(">p1\nAAAA\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/api/fs/list", params={"path": str(tmp_path.resolve())})

    assert response.status_code == 200
    assert response.json()[0]["name"] == "sample.faa"


def test_fs_list_endpoint_rejects_relative_paths():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.get("/api/fs/list", params={"path": "relative/path"})

    assert response.status_code == 400


def test_fs_search_endpoint_returns_matching_rows(tmp_path):
    (tmp_path / "sample.faa").write_text(">p1\nAAAA\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get(
        "/api/fs/search",
        params={"root": str(tmp_path.resolve()), "q": "sample"},
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "sample.faa"


def test_plan_endpoint_returns_structured_plan(monkeypatch):
    client = TestClient(create_app())

    def fake_plan_from_message(message, bundles, client):
        bundle = bundles[0]
        return {
            "assistant_message": "planned",
            "execution_plan": {
                "bundle_type": bundle.bundle_type,
                "input_items": [bundle.model_dump()],
                "stage_order": ["prefilter"],
                "parameter_overrides": {},
                "output_root": bundle.output_root,
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "planned",
            },
            "plan_warnings": [],
        }

    monkeypatch.setattr("thermo_mining.web.routes_api_plan.plan_from_message", fake_plan_from_message)

    response = client.post(
        "/api/plan",
        json={
            "message": "plan this",
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
    assert response.json()["assistant_message"] == "planned"


def test_plan_endpoint_returns_422_for_invalid_body():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post("/api/plan", json={"message": "plan this"})

    assert response.status_code == 422


def test_plan_endpoint_uses_dependency_override(monkeypatch):
    app = create_app()
    client = TestClient(app)
    fake_llm_client = object()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    captured: dict[str, object] = {}

    def fake_plan_from_message(message, bundles, client):
        captured["client"] = client
        bundle = bundles[0]
        return {
            "assistant_message": "planned",
            "execution_plan": {
                "bundle_type": bundle.bundle_type,
                "input_items": [bundle.model_dump()],
                "stage_order": ["prefilter"],
                "parameter_overrides": {},
                "output_root": bundle.output_root,
                "resume_policy": "if_possible",
                "requires_confirmation": True,
                "explanation": "planned",
            },
            "plan_warnings": [],
        }

    monkeypatch.setattr("thermo_mining.web.routes_api_plan.plan_from_message", fake_plan_from_message)

    response = client.post(
        "/api/plan",
        json={
            "message": "plan this",
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
    assert captured["client"] is fake_llm_client
