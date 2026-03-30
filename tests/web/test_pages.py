import warnings

from fastapi.testclient import TestClient

from thermo_mining.web.app import create_app


def test_index_page_contains_expected_console_sections():
    client = TestClient(create_app())

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        response = client.get("/")

    assert response.status_code == 200
    assert 'name="viewport"' in response.text
    assert "Chat" in response.text
    assert "Plan Review" in response.text
    assert "Run Monitor" in response.text
    assert "Artifacts" in response.text


def test_static_console_assets_are_mounted():
    client = TestClient(create_app())

    response = client.get("/static/console.css")

    assert response.status_code == 200
    assert "font-family" in response.text
    assert "#file-browser-results" in response.text
    assert "white-space: pre-wrap" in response.text
    assert "@media (max-width: 900px)" in response.text
