from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
    monkeypatch.setattr(gateway_main, "AGENT_RUN_DB_PATH", tmp_path / "agent_manager.db")
    monkeypatch.setattr(gateway_main, "_run_manager", None)
    return TestClient(gateway_main.app)


def test_setup_validate_and_save(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.delenv("OPENCOMMOTION_API_KEYS", raising=False)
    monkeypatch.setattr(gateway_main, "ENV_PATH", tmp_path / ".env")

    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        invalid = client.post(
            "/v1/setup/validate",
            json={"values": {"OPENCOMMOTION_LLM_PROVIDER": "not-a-provider"}},
        )
        assert invalid.status_code == 200
        payload = invalid.json()
        assert payload["ok"] is False
        assert payload["errors"]

        saved = client.post(
            "/v1/setup/state",
            json={
                "values": {
                    "OPENCOMMOTION_LLM_PROVIDER": "heuristic",
                    "OPENCOMMOTION_AUTH_MODE": "api-key",
                    "OPENCOMMOTION_API_KEYS": "alpha-key",
                }
            },
        )
        assert saved.status_code == 200
        saved_payload = saved.json()
        assert saved_payload["ok"] is True
        assert saved_payload["restart_required"] is False
        assert saved_payload["applied_runtime"] is True

        state = client.get("/v1/setup/state")
        assert state.status_code == 200
        state_payload = state.json()["state"]
        assert state_payload["OPENCOMMOTION_LLM_PROVIDER"] == "heuristic"
        assert state_payload["OPENCOMMOTION_API_KEYS"] == "********"

        env_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "OPENCOMMOTION_LLM_PROVIDER=heuristic" in env_text
        assert "OPENCOMMOTION_API_KEYS=alpha-key" in env_text


def test_agent_run_lifecycle_and_event_envelope(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.delenv("OPENCOMMOTION_API_KEYS", raising=False)

    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        with client.websocket_connect("/v1/events/ws") as ws:
            created = client.post("/v1/agent-runs", json={"label": "demo-run", "auto_run": False})
            assert created.status_code == 200
            run = created.json()["run"]
            run_id = run["run_id"]

            event = ws.receive_json()
            assert event["event_type"] == "agent.run.state"
            assert event["payload"]["run_id"] == run_id

        enqueue = client.post(
            f"/v1/agent-runs/{run_id}/enqueue",
            json={"prompt": "moonwalk adoption chart"},
        )
        assert enqueue.status_code == 200

        control = client.post(
            f"/v1/agent-runs/{run_id}/control",
            json={"action": "run_once"},
        )
        assert control.status_code == 200
        run_after = control.json()["run"]
        assert run_after["queue"]["done"] >= 1

        fetched = client.get(f"/v1/agent-runs/{run_id}")
        assert fetched.status_code == 200
        state = fetched.json()["run"]
        assert state["queue"]["done"] >= 1


def test_agent_run_control_actions_pause_resume_stop_drain(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.delenv("OPENCOMMOTION_API_KEYS", raising=False)

    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        created = client.post("/v1/agent-runs", json={"label": "control-run", "auto_run": False})
        assert created.status_code == 200
        run_id = created.json()["run"]["run_id"]

        paused = client.post(f"/v1/agent-runs/{run_id}/control", json={"action": "pause"})
        assert paused.status_code == 200
        assert paused.json()["run"]["status"] == "paused"

        resumed = client.post(f"/v1/agent-runs/{run_id}/control", json={"action": "resume"})
        assert resumed.status_code == 200
        assert resumed.json()["run"]["status"] == "idle"

        enqueue_a = client.post(f"/v1/agent-runs/{run_id}/enqueue", json={"prompt": "first prompt"})
        assert enqueue_a.status_code == 200
        enqueue_b = client.post(f"/v1/agent-runs/{run_id}/enqueue", json={"prompt": "second prompt"})
        assert enqueue_b.status_code == 200

        drained = client.post(f"/v1/agent-runs/{run_id}/control", json={"action": "drain"})
        assert drained.status_code == 200
        drained_run = drained.json()["run"]
        assert drained_run["queue"]["done"] >= 2
        assert drained_run["queue"]["queued"] == 0

        stopped = client.post(f"/v1/agent-runs/{run_id}/control", json={"action": "stop"})
        assert stopped.status_code == 200
        assert stopped.json()["run"]["status"] == "stopped"


def test_api_key_auth_enforced_when_keys_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.setenv("OPENCOMMOTION_API_KEYS", "test-key")

    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        denied = client.post(
            "/v1/orchestrate",
            json={"session_id": "auth-test", "prompt": "moonwalk adoption chart"},
        )
        assert denied.status_code == 401

        allowed = client.post(
            "/v1/orchestrate",
            headers={"x-api-key": "test-key"},
            json={"session_id": "auth-test", "prompt": "moonwalk adoption chart"},
        )
        assert allowed.status_code == 200


def test_websocket_auth_enforced_when_keys_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_AUTH_MODE", "api-key")
    monkeypatch.setenv("OPENCOMMOTION_API_KEYS", "ws-key")

    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/events/ws"):
                pass

        with client.websocket_connect("/v1/events/ws?api_key=ws-key") as ws:
            ws.send_text("ping")
