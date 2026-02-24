from __future__ import annotations

from statistics import median
from time import perf_counter

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


def test_orchestrate_median_latency_under_threshold(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)

    durations_ms: list[float] = []
    for idx in range(7):
        started = perf_counter()
        res = c.post(
            "/v1/orchestrate",
            json={"session_id": "perf-session", "prompt": f"perf run {idx} moonwalk adoption chart"},
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        assert res.status_code == 200
        durations_ms.append(elapsed_ms)

    median_ms = median(durations_ms)
    assert median_ms < 2500, f"median orchestrate latency too high: {median_ms:.1f}ms"
