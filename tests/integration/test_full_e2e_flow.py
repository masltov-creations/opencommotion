from __future__ import annotations

import json

from fastapi.testclient import TestClient

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.gateway.app import main as gateway_main
from services.orchestrator.app.main import app as orchestrator_app


def test_full_e2e_turn_artifact_recall_and_ws_event(tmp_path, monkeypatch) -> None:
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

    client = TestClient(gateway_main.app)
    prompt = "moonwalk globe adoption pie"

    with client.websocket_connect("/v1/events/ws") as ws:
        orchestrate = client.post(
            "/v1/orchestrate",
            json={"session_id": "e2e-session", "prompt": prompt},
        )
        assert orchestrate.status_code == 200
        turn = orchestrate.json()

        assert turn["session_id"] == "e2e-session"
        assert turn["text"].startswith("OpenCommotion:")
        assert len(turn["visual_strokes"]) >= 5
        assert len(turn["visual_patches"]) >= 5
        assert turn["voice"]["voice"] == "opencommotion-local"
        assert len(turn["voice"]["segments"]) == 1

        ws_event = ws.receive_json()

    assert ws_event["event_type"] == "gateway.event"
    assert ws_event["payload"]["turn_id"] == turn["turn_id"]
    assert ws_event["payload"]["text"] == turn["text"]
    assert ws_event["payload"]["voice"]["segments"][0]["audio_uri"].startswith("memory://")

    save = client.post(
        "/v1/artifacts/save",
        json={
            "title": "Moonwalk Globe Demo",
            "summary": turn["text"],
            "tags": ["moonwalk", "e2e"],
            "saved_by": "test-suite",
        },
    )
    assert save.status_code == 200
    save_payload = save.json()
    assert save_payload["ok"] is True

    artifact_id = save_payload["artifact"]["artifact_id"]
    manifest_path = bundle_root / artifact_id / "1.0.0" / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["title"] == "Moonwalk Globe Demo"
    assert "moonwalk" in manifest["tags"]

    search = client.get("/v1/artifacts/search", params={"q": "moonwalk"})
    assert search.status_code == 200
    search_results = search.json()["results"]
    assert any(result["artifact_id"] == artifact_id for result in search_results)

    recall = client.post(f"/v1/artifacts/recall/{artifact_id}")
    assert recall.status_code == 200
    recall_payload = recall.json()
    assert recall_payload["ok"] is True
    assert recall_payload["artifact"]["artifact_id"] == artifact_id
    assert recall_payload["artifact"]["title"] == "Moonwalk Globe Demo"
