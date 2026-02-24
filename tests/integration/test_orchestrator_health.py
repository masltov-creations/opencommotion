from fastapi.testclient import TestClient

from services.orchestrator.app.main import app


def test_orchestrator_health() -> None:
    c = TestClient(app)
    res = c.get('/health')
    assert res.status_code == 200
    assert res.json()['service'] == 'orchestrator'
