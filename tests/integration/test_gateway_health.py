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
