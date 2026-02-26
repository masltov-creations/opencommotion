from __future__ import annotations

from fastapi.testclient import TestClient

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.gateway.app import main as gateway_main
from services.orchestrator.app.main import app as orchestrator_app
from services.orchestrator.app import main as orchestrator_main
from services.scene_v2 import SceneV2Store


def _client_with_v2_scene_runtime(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.delenv("OPENCOMMOTION_API_KEYS", raising=False)

    db_path = tmp_path / "artifacts.db"
    bundle_root = tmp_path / "bundles"
    monkeypatch.setattr(
        gateway_main,
        "registry",
        ArtifactRegistry(db_path=str(db_path), bundle_root=str(bundle_root)),
    )
    monkeypatch.setattr(gateway_main, "scene_store_v2", SceneV2Store(tmp_path / "scenes"))

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


def test_v2_orchestrate_returns_scene_patch_envelope(tmp_path, monkeypatch) -> None:
    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    res = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-fish",
            "scene_id": "fishbowl-main",
            "prompt": "draw a fish bowl with a fish swimming in it",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["version"] == "v2"
    assert payload["scene_id"] == "fishbowl-main"
    assert payload["base_revision"] == 0
    assert payload["revision"] == 1
    assert isinstance(payload["patches"], list) and payload["patches"]
    assert any(row["op"] == "createEntity" for row in payload["patches"])
    assert isinstance(payload.get("legacy_visual_patches", []), list)

    scene_state = c.get("/v2/scenes/fishbowl-main")
    assert scene_state.status_code == 200
    scene = scene_state.json()["scene"]
    assert scene["revision"] == 1
    assert scene["entity_count"] >= 2


def test_v2_followup_bloop_mutates_without_bowl_rebuild(tmp_path, monkeypatch) -> None:
    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    first = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-followup",
            "scene_id": "fish-followup",
            "prompt": "draw a fish bowl with a fish swimming in it",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    first_revision = int(first_payload["revision"])

    second = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-followup",
            "scene_id": "fish-followup",
            "base_revision": first_revision,
            "prompt": "make the fish blooop",
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    ops = second_payload["patches"]
    assert second_payload["base_revision"] == first_revision
    assert second_payload["revision"] == first_revision + 1
    assert all(row["op"] != "destroyEntity" for row in ops)
    assert all(
        not (row["op"] == "createEntity" and str(row.get("kind", "")).lower() == "bowl")
        for row in ops
    )
    assert any(row["op"] in {"createBehavior", "updateBehavior", "trigger", "updateEntity", "setUniform"} for row in ops)


def test_v2_revision_conflict_and_snapshot_restore(tmp_path, monkeypatch) -> None:
    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    first = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-revision",
            "scene_id": "revision-scene",
            "prompt": "draw a box",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()

    conflict = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-revision",
            "scene_id": "revision-scene",
            "base_revision": 0,
            "prompt": "draw a triangle",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"] == "revision_conflict"

    snap = c.post(
        "/v2/scenes/revision-scene/snapshot",
        json={"snapshot_name": "before-restore", "persist_artifact": False},
    )
    assert snap.status_code == 200
    snapshot_id = snap.json()["snapshot"]["snapshot_id"]
    assert snapshot_id == "before-restore"

    restore = c.post(
        "/v2/scenes/revision-scene/restore",
        json={"snapshot_id": snapshot_id},
    )
    assert restore.status_code == 200
    restored = restore.json()["restored"]
    assert restored["scene_id"] == "revision-scene"


def test_v2_runtime_capabilities_includes_limits_and_recipes(tmp_path, monkeypatch) -> None:
    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    caps = c.get("/v2/runtime/capabilities")
    assert caps.status_code == 200
    payload = caps.json()
    assert payload["version"] == "v2"
    assert "three-webgl" in payload["renderers"]
    assert payload["features"]["shaderRecipes"] is True
    assert payload["limits"]["max_patch_ops_per_turn"] >= 1
    assert isinstance(payload.get("shader_recipes", []), list)


def test_v2_turn_without_visual_delta_emits_agent_context_reminder(tmp_path, monkeypatch) -> None:
    def no_visual_worker(_prompt: str) -> list[dict]:
        return [
            {
                "stroke_id": "note-only",
                "kind": "annotateInsight",
                "params": {"text": "text-only response"},
                "timing": {"start_ms": 0, "duration_ms": 120, "easing": "linear"},
            }
        ]

    monkeypatch.setattr(orchestrator_main, "generate_visual_strokes", no_visual_worker)

    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    res = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-reminder",
            "scene_id": "reminder-scene",
            "prompt": "explain why",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    warnings = payload.get("warnings", [])
    assert any(str(row).startswith("agent_context_reminder_applied") for row in warnings)


def test_v2_orchestrate_applies_prompt_rewrite_and_scene_request_flow(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_rewrite(prompt: str, *, context: str, first_turn: bool):
        calls.append({"prompt": prompt, "context": context, "first_turn": first_turn})
        if len(calls) == 1:
            return "update fish behavior to bloop", {"scene_request": True, "warnings": ["prompt_rewrite_scene_request:mock"]}
        return "draw a fish bowl with a fish swimming in it", {"scene_request": False, "warnings": ["prompt_rewrite_provider_applied:mock"]}

    monkeypatch.setattr(gateway_main, "rewrite_visual_prompt", fake_rewrite)
    c = _client_with_v2_scene_runtime(tmp_path, monkeypatch)
    res = c.post(
        "/v2/orchestrate",
        json={
            "session_id": "v2-rewrite-flow",
            "scene_id": "rewrite-scene",
            "prompt": "make the fish blooop",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    warnings = payload.get("warnings", [])
    assert any(str(row).startswith("prompt_rewrite_applied:") for row in warnings)
    assert "agent_scene_request_honored" in warnings
    assert len(calls) >= 2
