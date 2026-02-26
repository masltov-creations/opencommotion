from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.scene_v2.engine import new_scene_state, scene_summary


class SceneV2Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._scenes: dict[str, dict[str, Any]] = {}

    def _scene_dir(self, scene_id: str) -> Path:
        return self.root / scene_id

    def _autosave_path(self, scene_id: str) -> Path:
        return self._scene_dir(scene_id) / "autosave.json"

    def _snapshot_dir(self, scene_id: str) -> Path:
        return self._scene_dir(scene_id) / "snapshots"

    def _load_scene(self, scene_id: str) -> dict[str, Any]:
        auto_path = self._autosave_path(scene_id)
        if auto_path.exists():
            try:
                loaded = json.loads(auto_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                loaded.setdefault("scene_id", scene_id)
                loaded.setdefault("revision", 0)
                loaded.setdefault("entities", {})
                loaded.setdefault("materials", {})
                loaded.setdefault("behaviors", {})
                loaded.setdefault("bindings", {"entity_to_material": {}})
                loaded.setdefault("applied_op_ids", [])
                loaded.setdefault("id_aliases", {})
                loaded.setdefault("counters", {})
                loaded.setdefault("uniform_update_at", {})
                loaded.setdefault("trigger_log", [])
                loaded.setdefault("warnings", [])
                return loaded
        return new_scene_state(scene_id)

    def get_or_create(self, scene_id: str) -> dict[str, Any]:
        key = str(scene_id).strip() or "default"
        scene = self._scenes.get(key)
        if scene is None:
            scene = self._load_scene(key)
            self._scenes[key] = scene
        return scene

    def save_scene(self, scene_id: str) -> Path:
        scene = self.get_or_create(scene_id)
        scene_dir = self._scene_dir(scene_id)
        scene_dir.mkdir(parents=True, exist_ok=True)
        path = self._autosave_path(scene_id)
        payload = {
            **scene,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def autosave(self, scene_id: str) -> dict[str, Any]:
        path = self.save_scene(scene_id)
        return {"scene_id": scene_id, "snapshot_id": "autosave", "path": str(path)}

    def snapshot(self, scene_id: str, name: str = "") -> dict[str, Any]:
        scene = self.get_or_create(scene_id)
        snap_id = (name or "").strip() or str(uuid4())
        snap_dir = self._snapshot_dir(scene_id)
        snap_dir.mkdir(parents=True, exist_ok=True)
        path = snap_dir / f"{snap_id}.json"
        payload = {
            **scene,
            "snapshot_id": snap_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.save_scene(scene_id)
        return {"scene_id": scene_id, "snapshot_id": snap_id, "path": str(path), "summary": scene_summary(scene)}

    def restore(self, scene_id: str, snapshot_id: str) -> dict[str, Any]:
        path = self._snapshot_dir(scene_id) / f"{snapshot_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"snapshot '{snapshot_id}' was not found")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("snapshot payload is invalid")
        loaded["scene_id"] = scene_id
        self._scenes[scene_id] = loaded
        self.save_scene(scene_id)
        return {"scene_id": scene_id, "snapshot_id": snapshot_id, "summary": scene_summary(loaded)}

    def list_snapshots(self, scene_id: str) -> list[dict[str, Any]]:
        snap_dir = self._snapshot_dir(scene_id)
        if not snap_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(snap_dir.glob("*.json")):
            rows.append({"snapshot_id": path.stem, "path": str(path), "updated_at": path.stat().st_mtime})
        rows.sort(key=lambda row: row["updated_at"], reverse=True)
        return rows

    def state_view(self, scene_id: str) -> dict[str, Any]:
        scene = self.get_or_create(scene_id)
        return {
            "scene": scene_summary(scene),
            "snapshots": self.list_snapshots(scene_id),
        }


__all__ = ["SceneV2Store"]
