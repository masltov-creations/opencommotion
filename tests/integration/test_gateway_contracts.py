from __future__ import annotations

from fastapi.testclient import TestClient

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.agents.visual.quality import evaluate_market_growth_scene
from services.gateway.app import main as gateway_main
from services.orchestrator.app.main import app as orchestrator_app


def _client_with_inprocess_orchestrator(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.delenv("OPENCOMMOTION_API_KEYS", raising=False)
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


def test_compile_rejects_invalid_stroke_schema(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.post(
        "/v1/brush/compile",
        json={
            "strokes": [
                {
                    "stroke_id": "bad-1",
                    "kind": "invalidKind",
                    "params": {},
                    "timing": {"start_ms": 0, "duration_ms": 10, "easing": "linear"},
                }
            ]
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "schema_validation_failed"


def test_voice_endpoints_work_without_external_engines(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    transcribe = c.post(
        "/v1/voice/transcribe",
        files={"audio": ("sample.wav", b"moonwalk adoption chart", "audio/wav")},
    )
    assert transcribe.status_code == 200
    transcript = transcribe.json()["transcript"]
    assert transcript["final"]

    synth = c.post("/v1/voice/synthesize", json={"text": "render voice now"})
    assert synth.status_code == 200
    voice = synth.json()["voice"]
    uri = voice["segments"][0]["audio_uri"]
    assert uri.startswith("/v1/audio/")

    audio_get = c.get(uri)
    assert audio_get.status_code == 200
    assert audio_get.headers["content-type"] in {"audio/x-wav", "audio/wav", "application/octet-stream"}


def test_artifact_modes_pin_archive_and_schema_guard(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    first = c.post(
        "/v1/artifacts/save",
        json={
            "title": "Adoption Moonwalk Story",
            "summary": "A chart showing rapid growth and uptake.",
            "tags": ["moonwalk", "adoption"],
        },
    )
    assert first.status_code == 200
    first_id = first.json()["artifact"]["artifact_id"]

    second = c.post(
        "/v1/artifacts/save",
        json={
            "title": "Financial Minutes",
            "summary": "Quarterly budget review",
            "tags": ["finance"],
        },
    )
    assert second.status_code == 200
    second_id = second.json()["artifact"]["artifact_id"]

    semantic = c.get("/v1/artifacts/search", params={"q": "uptake growth", "mode": "semantic"})
    assert semantic.status_code == 200
    semantic_results = semantic.json()["results"]
    assert semantic_results
    assert semantic_results[0]["match_mode"] == "semantic"

    hybrid = c.get("/v1/artifacts/search", params={"q": "moonwalk", "mode": "hybrid"})
    assert hybrid.status_code == 200
    assert hybrid.json()["results"][0]["match_mode"] == "hybrid"

    pin = c.post(f"/v1/artifacts/pin/{first_id}", json={"value": True})
    assert pin.status_code == 200
    assert pin.json()["pinned"] is True

    archive = c.post(f"/v1/artifacts/archive/{second_id}", json={"value": True})
    assert archive.status_code == 200
    assert archive.json()["archived"] is True

    filtered = c.get("/v1/artifacts/search", params={"q": "", "mode": "lexical"})
    assert filtered.status_code == 200
    filtered_ids = [row["artifact_id"] for row in filtered.json()["results"]]
    assert first_id in filtered_ids
    assert second_id not in filtered_ids

    bad_bundle = c.post(
        "/v1/artifacts/save",
        json={
            "title": "Broken Asset",
            "summary": "missing required schema fields",
            "tags": ["broken"],
            "assets": [{"path": "a.txt", "type": "text/plain"}],
        },
    )
    assert bad_bundle.status_code == 422
    assert bad_bundle.json()["detail"]["error"] == "schema_validation_failed"


def test_market_growth_graph_quality_report_is_compatible(tmp_path, monkeypatch) -> None:
    c = _client_with_inprocess_orchestrator(tmp_path, monkeypatch)
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "market-growth-eval",
            "prompt": (
                "animated presentation showcasing market growth and increases in segmented attach within markets; "
                "graphs should grow as timeline tick proceeds"
            ),
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert "quality_report" in payload
    assert payload["quality_report"]["ok"] is True
    report = evaluate_market_growth_scene(payload["visual_patches"])
    assert report["ok"] is True
    assert "adoption_curve_growth_trend" in report["checks"]
    assert "segmented_attach_targets_valid" in report["checks"]
