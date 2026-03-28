from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app


def test_fs_list_endpoint_returns_directory_rows(tmp_path):
    (tmp_path / "sample.faa").write_text(">p1\nAAAA\n", encoding="utf-8")
    client = TestClient(create_app())

    response = client.get("/api/fs/list", params={"path": str(tmp_path.resolve())})

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
