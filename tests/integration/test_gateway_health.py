from fastapi.testclient import TestClient

from services.gateway.app.main import app


def test_gateway_health() -> None:
    c = TestClient(app)
    res = c.get('/health')
    assert res.status_code == 200
    assert res.json()['service'] == 'gateway'


def test_gateway_serves_ui_index_when_dist_available() -> None:
    c = TestClient(app)
    res = c.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")


def test_gateway_serves_ui_assets_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.setenv("OPENCOMMOTION_API_KEYS", "dev-opencommotion-key")
    c = TestClient(app)

    index_res = c.get("/")
    assert index_res.status_code == 200
    html = index_res.text
    marker = "/assets/"
    start = html.find(marker)
    assert start != -1

    end = html.find('"', start)
    assert end != -1
    asset_path = html[start:end]

    asset_res = c.get(asset_path)
    assert asset_res.status_code == 200
