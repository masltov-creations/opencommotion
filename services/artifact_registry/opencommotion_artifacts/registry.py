from __future__ import annotations

import json
import os
import sqlite3
import uuid
from hashlib import sha1
from math import sqrt
from re import findall
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "artifacts" / "artifacts.db"
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / "data" / "artifacts" / "bundles"
EMBED_DIM = 96
SYNONYM_MAP = {
    "adoption": ["growth", "uptake", "onboarding"],
    "chart": ["graph", "plot", "curve"],
    "pie": ["distribution", "segment", "slice"],
    "moonwalk": ["dance", "glide", "movement"],
    "voice": ["speech", "audio", "narration"],
    "artifact": ["memory", "bundle", "snapshot"],
}


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
                    embedding_json TEXT NOT NULL DEFAULT '[]',
                    content_text TEXT NOT NULL DEFAULT '',
                    saved_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        with self._conn() as conn:
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
            }
            if "embedding_json" not in columns:
                conn.execute(
                    "ALTER TABLE artifacts ADD COLUMN embedding_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "content_text" not in columns:
                conn.execute(
                    "ALTER TABLE artifacts ADD COLUMN content_text TEXT NOT NULL DEFAULT ''"
                )

    def save_artifact(self, bundle: dict[str, Any], saved_by: str = "system") -> dict[str, Any]:
        artifact_id = bundle.get("artifact_id") or str(uuid.uuid4())
        version = bundle.get("version", "1.0.0")
        title = bundle.get("title", "Untitled artifact")
        summary = bundle.get("summary", "")
        tags = bundle.get("tags", [])
        scene_hash = bundle.get("scene_hash", "")
        content_text = " ".join([title, summary, " ".join(tags)]).strip()
        embedding = self._embed_text(content_text)

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
                    pinned, archived, scene_hash, embedding_json, content_text,
                    saved_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    tags_json=excluded.tags_json,
                    bundle_path=excluded.bundle_path,
                    scene_hash=excluded.scene_hash,
                    embedding_json=excluded.embedding_json,
                    content_text=excluded.content_text,
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
                    json.dumps(embedding),
                    content_text,
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
            "embedding_dim": EMBED_DIM,
        }

    def search(
        self,
        query: str,
        limit: int = 30,
        mode: str = "lexical",
    ) -> list[dict[str, Any]]:
        normalized_mode = mode.lower()
        if normalized_mode not in {"lexical", "semantic", "hybrid"}:
            normalized_mode = "lexical"

        if not query.strip():
            return self._search_lexical(query, limit)

        if normalized_mode == "lexical":
            return self._search_lexical(query, limit)

        if normalized_mode == "semantic":
            return self._search_semantic(query, limit)

        return self._search_hybrid(query, limit)

    def _search_lexical(self, query: str, limit: int) -> list[dict[str, Any]]:
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

        results: list[dict[str, Any]] = []
        total = max(len(rows), 1)
        for idx, row in enumerate(rows):
            score = round(1.0 - (idx / total), 6)
            results.append(self._row_to_result(row, score=score, match_mode="lexical"))
        return results

    def _search_semantic(self, query: str, limit: int) -> list[dict[str, Any]]:
        query_embedding = self._embed_text(query)
        rows = self._all_active_rows()
        ranked: list[tuple[float, sqlite3.Row]] = []

        for row in rows:
            embedding = self._decode_embedding(row["embedding_json"])
            score = self._cosine_similarity(query_embedding, embedding)
            if score <= 0:
                continue
            if row["pinned"]:
                score += 0.05
            ranked.append((score, row))

        ranked.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
        return [
            self._row_to_result(row, score=round(score, 6), match_mode="semantic")
            for score, row in ranked[:limit]
        ]

    def _search_hybrid(self, query: str, limit: int) -> list[dict[str, Any]]:
        lexical = self._search_lexical(query, limit * 4)
        semantic = self._search_semantic(query, limit * 4)
        merged: dict[str, dict[str, Any]] = {}

        for item in lexical:
            merged[item["artifact_id"]] = {
                **item,
                "_lexical": item["score"],
                "_semantic": 0.0,
            }

        for item in semantic:
            existing = merged.get(item["artifact_id"])
            if existing is None:
                merged[item["artifact_id"]] = {
                    **item,
                    "_lexical": 0.0,
                    "_semantic": item["score"],
                }
            else:
                existing["_semantic"] = item["score"]

        ranked = []
        for artifact in merged.values():
            combined = round((artifact["_semantic"] * 0.65) + (artifact["_lexical"] * 0.35), 6)
            artifact["score"] = combined
            artifact["match_mode"] = "hybrid"
            ranked.append(artifact)

        ranked.sort(
            key=lambda row: (
                row["score"],
                row["pinned"],
                row["updated_at"],
            ),
            reverse=True,
        )

        trimmed = []
        for row in ranked[:limit]:
            row.pop("_lexical", None)
            row.pop("_semantic", None)
            trimmed.append(row)
        return trimmed

    def _all_active_rows(self) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                """
                SELECT artifact_id, title, summary, tags_json, bundle_path, pinned, archived, updated_at, embedding_json
                FROM artifacts
                WHERE archived = 0
                ORDER BY pinned DESC, updated_at DESC
                """
            ).fetchall()

    def _row_to_result(
        self,
        row: sqlite3.Row,
        score: float,
        match_mode: str,
    ) -> dict[str, Any]:
        return {
            "artifact_id": row["artifact_id"],
            "title": row["title"],
            "summary": row["summary"],
            "tags": json.loads(row["tags_json"]),
            "bundle_path": row["bundle_path"],
            "pinned": bool(row["pinned"]),
            "score": score,
            "match_mode": match_mode,
            "updated_at": row["updated_at"],
        }

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT artifact_id, title, summary, tags_json, bundle_path, pinned, archived, embedding_json
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
            "embedding_dim": len(self._decode_embedding(row["embedding_json"])),
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

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        if dot <= 0:
            return 0.0
        return dot

    def _embed_text(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * EMBED_DIM

        vector = [0.0] * EMBED_DIM
        for token in tokens:
            idx = self._stable_bucket(token)
            vector[idx] += 1.0

        norm = sqrt(sum(v * v for v in vector)) or 1.0
        return [round(v / norm, 8) for v in vector]

    @staticmethod
    def _decode_embedding(raw: str) -> list[float]:
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return [float(v) for v in value]
        except json.JSONDecodeError:
            return [0.0] * EMBED_DIM
        return [0.0] * EMBED_DIM

    @staticmethod
    def _stable_bucket(token: str) -> int:
        digest = sha1(token.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % EMBED_DIM

    def _tokenize(self, text: str) -> list[str]:
        tokens: list[str] = []
        for token in findall(r"[a-z0-9]+", text.lower()):
            norm = self._normalize_token(token)
            if not norm:
                continue
            tokens.append(norm)
            for synonym in SYNONYM_MAP.get(norm, []):
                tokens.append(synonym)
        return tokens

    @staticmethod
    def _normalize_token(token: str) -> str:
        if len(token) > 4 and token.endswith("ing"):
            return token[:-3]
        if len(token) > 3 and token.endswith("ed"):
            return token[:-2]
        if len(token) > 3 and token.endswith("s"):
            return token[:-1]
        return token
