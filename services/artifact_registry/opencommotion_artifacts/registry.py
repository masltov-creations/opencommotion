from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "artifacts" / "artifacts.db"
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "data" / "artifacts" / "bundles"


class ArtifactRegistry:
    def __init__(self, db_path: str | None = None, bundle_root: str | None = None) -> None:
        self.db_path = db_path or os.getenv(
            "ARTIFACT_DB_PATH", str(DEFAULT_DB_PATH)
        )
        self.bundle_root = Path(
            bundle_root
            or os.getenv(
                "ARTIFACT_BUNDLE_ROOT",
                str(DEFAULT_BUNDLE_ROOT),
            )
        )
        self.bundle_root.mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    tags_json TEXT NOT NULL,
                    bundle_path TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    scene_hash TEXT,
                    saved_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save_artifact(self, bundle: dict[str, Any], saved_by: str = "system") -> dict[str, Any]:
        artifact_id = bundle.get("artifact_id") or str(uuid.uuid4())
        version = bundle.get("version", "1.0.0")
        title = bundle.get("title", "Untitled artifact")
        summary = bundle.get("summary", "")
        tags = bundle.get("tags", [])
        scene_hash = bundle.get("scene_hash", "")

        bundle_dir = self.bundle_root / artifact_id / version
        bundle_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "artifact_id": artifact_id,
            "version": version,
            "title": title,
            "summary": summary,
            "tags": tags,
            "scene_entrypoint": bundle.get("scene_entrypoint", "scene/entry.scene.json"),
            "assets": bundle.get("assets", []),
            "saved_by": saved_by,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, title, summary, tags_json, bundle_path,
                    pinned, archived, scene_hash, saved_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    tags_json=excluded.tags_json,
                    bundle_path=excluded.bundle_path,
                    scene_hash=excluded.scene_hash,
                    saved_by=excluded.saved_by,
                    updated_at=excluded.updated_at
                """,
                (
                    artifact_id,
                    title,
                    summary,
                    json.dumps(tags),
                    str(bundle_dir),
                    scene_hash,
                    saved_by,
                    now,
                    now,
                ),
            )

        return {
            "artifact_id": artifact_id,
            "title": title,
            "summary": summary,
            "tags": tags,
            "bundle_path": str(bundle_dir),
        }

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        q = f"%{query.lower()}%"
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT artifact_id, title, summary, tags_json, bundle_path, pinned, archived, updated_at
                FROM artifacts
                WHERE archived = 0
                  AND (lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(tags_json) LIKE ?)
                ORDER BY pinned DESC, updated_at DESC
                LIMIT ?
                """,
                (q, q, q, limit),
            ).fetchall()

        return [
            {
                "artifact_id": row["artifact_id"],
                "title": row["title"],
                "summary": row["summary"],
                "tags": json.loads(row["tags_json"]),
                "bundle_path": row["bundle_path"],
                "pinned": bool(row["pinned"]),
            }
            for row in rows
        ]

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT artifact_id, title, summary, tags_json, bundle_path, pinned, archived
                FROM artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "artifact_id": row["artifact_id"],
            "title": row["title"],
            "summary": row["summary"],
            "tags": json.loads(row["tags_json"]),
            "bundle_path": row["bundle_path"],
            "pinned": bool(row["pinned"]),
            "archived": bool(row["archived"]),
        }

    def pin(self, artifact_id: str, value: bool = True) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE artifacts SET pinned = ?, updated_at = ? WHERE artifact_id = ?",
                (1 if value else 0, datetime.now(timezone.utc).isoformat(), artifact_id),
            )
        return result.rowcount > 0

    def archive(self, artifact_id: str, value: bool = True) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE artifacts SET archived = ?, updated_at = ? WHERE artifact_id = ?",
                (1 if value else 0, datetime.now(timezone.utc).isoformat(), artifact_id),
            )
        return result.rowcount > 0
