from fastapi.testclient import TestClient

from services.orchestrator.app.main import app


def test_orchestrate_response_shape() -> None:
    c = TestClient(app)
    res = c.post('/v1/orchestrate', json={'session_id': 't1', 'prompt': 'moonwalk chart'})
    assert res.status_code == 200
    payload = res.json()
    assert 'text' in payload
    assert 'visual_strokes' in payload
    assert 'voice' in payload
    assert 'timeline' in payload
