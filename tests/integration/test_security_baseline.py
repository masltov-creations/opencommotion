from __future__ import annotations

from fastapi.testclient import TestClient

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.gateway.app import main as gateway_main
from services.orchestrator.app.main import app as orchestrator_app


def _client_with_inprocess_orchestrator(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "artifacts.db"
    bundle_root = tmp_path / "bundles"
    monkeypatch.setattr(
        gateway_main,
        "registry",
        ArtifactRegistry(db_path=str(db_path), bundle_root=str(bundle_root)),
    )

    original_async_client = gateway_main.httpx.AsyncClient

    class RoutedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            timeout = kwargs.get("timeout", 20)
            self._client = original_async_client(
                timeout=timeout,
                transport=gateway_main.httpx.ASGITransport(app=orchestrator_app),
                base_url="http://127.0.0.1:8001",
            )

        async def __aenter__(self):
            await self._client.__aenter__()
            return self._client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return await self._client.__aexit__(exc_type, exc_val, exc_tb)

    monkeypatch.setattr(gateway_main.httpx, "AsyncClient", RoutedAsyncClient)
    return TestClient(gateway_main.app)


def test_orchestrate_rejects_prompt_over_limit(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.post("/v1/orchestrate", json={"session_id": "s", "prompt": "x" * 4001})
    assert res.status_code == 422
    payload = res.json()["detail"]
    assert payload["error"] == "prompt_too_long"
    assert payload["max_chars"] == 4000


def test_transcribe_rejects_empty_audio_payload(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.post(
        "/v1/voice/transcribe",
        files={"audio": ("empty.wav", b"", "audio/wav")},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "empty_audio_payload"


def test_search_limit_is_capped_to_guard_resource_use(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    c.post(
        "/v1/artifacts/save",
        json={"title": "Artifact A", "summary": "summary", "tags": ["a"]},
    )
    c.post(
        "/v1/artifacts/save",
        json={"title": "Artifact B", "summary": "summary", "tags": ["b"]},
    )

    res = c.get("/v1/artifacts/search", params={"q": "artifact", "limit": 500})
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) <= 100
