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


def test_runtime_capabilities_expose_llm_and_voice(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.get("/v1/runtime/capabilities")
    assert res.status_code == 200
    payload = res.json()
    assert "llm" in payload
    assert "voice" in payload
    assert "selected_provider" in payload["llm"]
    assert "stt" in payload["voice"]
    assert "tts" in payload["voice"]


def test_orchestrate_fails_without_llm_fallback_when_provider_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENCOMMOTION_LLM_ALLOW_FALLBACK", "false")
    monkeypatch.setenv("OPENCOMMOTION_OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("OPENCOMMOTION_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    monkeypatch.setenv("OPENCOMMOTION_LLM_TIMEOUT_S", "0.5")

    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.post(
        "/v1/orchestrate",
        json={"session_id": "s", "prompt": "moonwalk adoption chart"},
    )
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert detail["error"] == "llm_engine_unavailable"
