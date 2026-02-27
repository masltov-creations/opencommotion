from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4


RunTurnExecutor = Callable[[str, str], Awaitable[dict]]
RunEventEmitter = Callable[[str, dict], Awaitable[None]]


@dataclass
class QueueItem:
    queue_id: int
    run_id: str
    session_id: str
    prompt: str


class AgentRunManager:
    def __init__(
        self,
        db_path: Path,
        turn_executor: RunTurnExecutor,
        event_emitter: RunEventEmitter,
        max_concurrent_turns: int = 3,
    ) -> None:
        self.db_path = db_path
        self.turn_executor = turn_executor
        self.event_emitter = event_emitter
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._worker: asyncio.Task | None = None
        self._max_concurrent_turns = max(1, max_concurrent_turns)
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._init_db()

    async def start(self) -> None:
        recovered = self._recover_inflight()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop(), name="opencommotion-agent-run-manager")
        for run_id in recovered:
            await self._emit_run_state(run_id, reason="recovered")
        self._wake.set()

    async def stop(self) -> None:
        task = self._worker
        if task is None:
            return
        task.cancel()
        self._wake.set()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._worker = None
        if self._active_tasks:
            for active in list(self._active_tasks):
                active.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    auto_run INTEGER NOT NULL DEFAULT 1,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    turn_id TEXT,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )

    def _recover_inflight(self) -> list[str]:
        now = _utc_now()
        with self._conn() as conn:
            queue_rows = conn.execute("SELECT DISTINCT run_id FROM queue WHERE status = 'processing'").fetchall()
            run_rows = conn.execute("SELECT run_id FROM runs WHERE status = 'running'").fetchall()
            run_ids = {row["run_id"] for row in queue_rows}
            run_ids.update(row["run_id"] for row in run_rows)
            if not run_ids:
                return []
            conn.execute(
                """
                UPDATE queue
                SET status = 'queued',
                    turn_id = NULL,
                    error = '',
                    updated_at = ?
                WHERE status = 'processing'
                """,
                (now,),
            )
            conn.execute(
                """
                UPDATE runs
                SET status = 'idle',
                    last_error = '',
                    updated_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
        return sorted(run_ids)

    def create_run(self, label: str, session_id: str | None = None, run_id: str | None = None, auto_run: bool = True) -> dict:
        now = _utc_now()
        resolved_run_id = run_id or str(uuid4())
        resolved_session_id = session_id or f"run-{resolved_run_id[:8]}"
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, session_id, label, status, auto_run, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_run_id,
                    resolved_session_id,
                    label,
                    "idle",
                    1 if auto_run else 0,
                    now,
                    now,
                ),
            )
        return self.get_run(resolved_run_id)

    def list_runs(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT run_id, session_id, label, status, auto_run, last_error, created_at, updated_at
                FROM runs
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._run_row_to_dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT run_id, session_id, label, status, auto_run, last_error, created_at, updated_at
                FROM runs WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            counts = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued_count,
                    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) AS processing_count,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count
                FROM queue
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        result = self._run_row_to_dict(row)
        result["queue"] = {
            "queued": int((counts["queued_count"] or 0)),
            "processing": int((counts["processing_count"] or 0)),
            "done": int((counts["done_count"] or 0)),
            "error": int((counts["error_count"] or 0)),
        }
        return result

    def enqueue(self, run_id: str, prompt: str) -> dict:
        now = _utc_now()
        if not prompt.strip():
            raise ValueError("prompt is required")
        with self._conn() as conn:
            run = conn.execute(
                "SELECT run_id, status, auto_run FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            row = conn.execute(
                """
                INSERT INTO queue (run_id, prompt, status, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?)
                RETURNING queue_id, run_id, prompt, status, created_at, updated_at
                """,
                (run_id, prompt, now, now),
            ).fetchone()

        if run["auto_run"] and run["status"] in {"idle", "running"}:
            self._wake.set()
        return {
            "queue_id": int(row["queue_id"]),
            "run_id": row["run_id"],
            "prompt": row["prompt"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def control(self, run_id: str, action: str) -> dict:
        valid = {"run_once", "pause", "resume", "stop", "drain"}
        if action not in valid:
            raise ValueError(f"unsupported action: {action}")

        if action == "pause":
            self._set_run_status(run_id, "paused")
            await self._emit_run_state(run_id, reason="pause")
            return self.get_run(run_id)

        if action == "resume":
            self._set_run_status(run_id, "idle")
            await self._emit_run_state(run_id, reason="resume")
            self._wake.set()
            return self.get_run(run_id)

        if action == "stop":
            self._set_run_status(run_id, "stopped")
            await self._emit_run_state(run_id, reason="stop")
            return self.get_run(run_id)

        if action == "run_once":
            await self._process_next_for_run(run_id, max_items=1, manual=True)
            return self.get_run(run_id)

        # drain
        await self._process_next_for_run(run_id, max_items=10_000, manual=True)
        return self.get_run(run_id)

    async def _worker_loop(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while len(self._active_tasks) < self._max_concurrent_turns:
                item = self._claim_next_queue_item(auto_only=True)
                if item is None:
                    break
                task = asyncio.create_task(self._process_queue_item(item))
                self._active_tasks.add(task)
                task.add_done_callback(self._handle_task_done)
            if not self._active_tasks:
                continue
            await asyncio.wait(self._active_tasks.copy(), return_when=asyncio.FIRST_COMPLETED)

    def _claim_next_queue_item(self, auto_only: bool) -> QueueItem | None:
        with self._conn() as conn:
            if auto_only:
                row = conn.execute(
                    """
                    SELECT q.queue_id, q.run_id, r.session_id, q.prompt
                    FROM queue q
                    JOIN runs r ON r.run_id = q.run_id
                    WHERE q.status = 'queued'
                      AND r.auto_run = 1
                      AND r.status IN ('idle', 'running')
                    ORDER BY q.queue_id ASC
                    LIMIT 1
                    """
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT q.queue_id, q.run_id, r.session_id, q.prompt
                    FROM queue q
                    JOIN runs r ON r.run_id = q.run_id
                    WHERE q.status = 'queued'
                    ORDER BY q.queue_id ASC
                    LIMIT 1
                    """
                ).fetchone()
            if row is None:
                return None
            now = _utc_now()
            conn.execute(
                "UPDATE queue SET status = 'processing', updated_at = ? WHERE queue_id = ?",
                (now, row["queue_id"]),
            )
            conn.execute(
                "UPDATE runs SET status = 'running', updated_at = ? WHERE run_id = ?",
                (now, row["run_id"]),
            )
        return QueueItem(
            queue_id=int(row["queue_id"]),
            run_id=row["run_id"],
            session_id=row["session_id"],
            prompt=row["prompt"],
        )

    async def _process_next_for_run(self, run_id: str, max_items: int, manual: bool) -> None:
        count = 0
        while count < max_items:
            item = self._claim_next_for_run(run_id=run_id, manual=manual)
            if item is None:
                break
            await self._process_queue_item(item)
            count += 1

    def _claim_next_for_run(self, run_id: str, manual: bool) -> QueueItem | None:
        with self._conn() as conn:
            run = conn.execute(
                "SELECT run_id, session_id, status FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            if not manual and run["status"] in {"paused", "stopped"}:
                return None
            row = conn.execute(
                """
                SELECT queue_id, run_id, prompt
                FROM queue
                WHERE run_id = ? AND status = 'queued'
                ORDER BY queue_id ASC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            now = _utc_now()
            conn.execute(
                "UPDATE queue SET status = 'processing', updated_at = ? WHERE queue_id = ?",
                (now, row["queue_id"]),
            )
            conn.execute(
                "UPDATE runs SET status = 'running', updated_at = ?, last_error = '' WHERE run_id = ?",
                (now, run_id),
            )
        return QueueItem(
            queue_id=int(row["queue_id"]),
            run_id=row["run_id"],
            session_id=run["session_id"],
            prompt=row["prompt"],
        )

    async def _process_queue_item(self, item: QueueItem) -> None:
        await self.event_emitter(
            "agent.turn.started",
            {
                "run_id": item.run_id,
                "queue_id": item.queue_id,
                "session_id": item.session_id,
                "prompt": item.prompt,
            },
        )
        try:
            payload = await self.turn_executor(item.session_id, item.prompt)
        except Exception as exc:  # noqa: BLE001
            now = _utc_now()
            with self._conn() as conn:
                conn.execute(
                    "UPDATE queue SET status = 'error', error = ?, updated_at = ? WHERE queue_id = ?",
                    (str(exc), now, item.queue_id),
                )
                conn.execute(
                    "UPDATE runs SET status = 'error', last_error = ?, updated_at = ? WHERE run_id = ?",
                    (str(exc), now, item.run_id),
                )
            await self.event_emitter(
                "agent.turn.failed",
                {
                    "run_id": item.run_id,
                    "queue_id": item.queue_id,
                    "session_id": item.session_id,
                    "error": str(exc),
                },
            )
            await self._emit_run_state(item.run_id, reason="turn_failed")
            return

        turn_id = str(payload.get("turn_id", ""))
        now = _utc_now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE queue SET status = 'done', turn_id = ?, error = '', updated_at = ? WHERE queue_id = ?",
                (turn_id, now, item.queue_id),
            )
            run = conn.execute(
                "SELECT status FROM runs WHERE run_id = ?",
                (item.run_id,),
            ).fetchone()
            next_status = "idle"
            if run and run["status"] == "stopped":
                next_status = "stopped"
            elif run and run["status"] == "paused":
                next_status = "paused"
            conn.execute(
                "UPDATE runs SET status = ?, last_error = '', updated_at = ? WHERE run_id = ?",
                (next_status, now, item.run_id),
            )
        await self.event_emitter(
            "agent.turn.completed",
            {
                "run_id": item.run_id,
                "queue_id": item.queue_id,
                "session_id": item.session_id,
                "turn_id": turn_id,
                "payload": payload,
            },
        )
        await self._emit_run_state(item.run_id, reason="turn_completed")
        self._wake.set()

    def _handle_task_done(self, task: asyncio.Task[None]) -> None:
        self._active_tasks.discard(task)
        try:
            task.exception()
        except asyncio.CancelledError:
            pass
        self._wake.set()

    def _set_run_status(self, run_id: str, status: str) -> None:
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status, _utc_now(), run_id),
            )
            if result.rowcount == 0:
                raise KeyError(run_id)

    async def _emit_run_state(self, run_id: str, reason: str) -> None:
        run = self.get_run(run_id)
        await self.event_emitter(
            "agent.run.state",
            {
                "run_id": run_id,
                "reason": reason,
                "state": run,
            },
        )

    @staticmethod
    def _run_row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "run_id": row["run_id"],
            "session_id": row["session_id"],
            "label": row["label"],
            "status": row["status"],
            "auto_run": bool(row["auto_run"]),
            "last_error": row["last_error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
