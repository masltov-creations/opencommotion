from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from time import perf_counter, sleep

import httpx
from fastapi.testclient import TestClient

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.gateway.app import main as gateway_main
from services.orchestrator.app.main import app as orchestrator_app

REAL_ASYNC_CLIENT = httpx.AsyncClient


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

    class RoutedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            timeout = kwargs.get("timeout", 20)
            self._client = REAL_ASYNC_CLIENT(
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


def test_agent_run_manager_recovers_processing_items_after_restart(tmp_path, monkeypatch) -> None:
    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        created = client.post(
            "/v1/agent-runs",
            json={"label": "recovery-run", "auto_run": False, "session_id": "recovery-session"},
        )
        assert created.status_code == 200
        run_id = created.json()["run"]["run_id"]

        enqueue = client.post(
            f"/v1/agent-runs/{run_id}/enqueue",
            json={"prompt": "resume me after restart"},
        )
        assert enqueue.status_code == 200

        now = datetime.now(timezone.utc).isoformat()
        manager_db = tmp_path / "agent_manager.db"
        with sqlite3.connect(manager_db) as conn:
            conn.execute(
                "UPDATE queue SET status = 'processing', updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )
            conn.execute(
                "UPDATE runs SET status = 'running', updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )
            conn.commit()

    # simulate process restart: app startup should recover in-flight queue items.
    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        run = client.get(f"/v1/agent-runs/{run_id}")
        assert run.status_code == 200
        run_state = run.json()["run"]
        assert run_state["status"] == "idle"
        assert run_state["queue"]["queued"] == 1
        assert run_state["queue"]["processing"] == 0

        processed = client.post(
            f"/v1/agent-runs/{run_id}/control",
            json={"action": "run_once"},
        )
        assert processed.status_code == 200
        processed_state = processed.json()["run"]
        assert processed_state["queue"]["done"] == 1
        assert processed_state["queue"]["error"] == 0


def test_agent_run_manager_handles_ten_sessions_within_threshold(tmp_path, monkeypatch) -> None:
    with _client_with_inprocess_orchestrator(tmp_path, monkeypatch) as client:
        run_ids: list[str] = []
        start = perf_counter()
        for idx in range(10):
            created = client.post(
                "/v1/agent-runs",
                json={
                    "label": f"soak-{idx}",
                    "session_id": f"soak-session-{idx}",
                    "auto_run": True,
                },
            )
            assert created.status_code == 200
            run_id = created.json()["run"]["run_id"]
            run_ids.append(run_id)
            queued = client.post(
                f"/v1/agent-runs/{run_id}/enqueue",
                json={"prompt": f"soak turn {idx}: moonwalk adoption chart"},
            )
            assert queued.status_code == 200

        pending = set(run_ids)
        completed: dict[str, dict] = {}
        deadline = perf_counter() + 45.0  # 45s: parallel orchestration may add latency on slow CI/dev machines

        while pending and perf_counter() < deadline:
            for run_id in list(pending):
                fetched = client.get(f"/v1/agent-runs/{run_id}")
                assert fetched.status_code == 200
                run_state = fetched.json()["run"]
                queue = run_state["queue"]
                if queue["done"] >= 1 or queue["error"] >= 1:
                    completed[run_id] = run_state
                    pending.remove(run_id)
            if pending:
                sleep(0.05)

        elapsed = perf_counter() - start
        assert not pending, f"runs did not complete in time: {sorted(pending)}"
        assert elapsed < 45.0, f"10-session completion latency too high: {elapsed:.2f}s"

        for run_id in run_ids:
            state = completed[run_id]
            assert state["queue"]["done"] >= 1, f"run {run_id} did not finish successfully"
            assert state["queue"]["error"] == 0, f"run {run_id} hit queue errors"
