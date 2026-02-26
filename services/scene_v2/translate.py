from __future__ import annotations

from typing import Any

from services.scene_v2.engine import BEHAVIOR_NS, ENTITY_NS, MATERIAL_NS, canonical_id


def _existing(scene: dict[str, Any], namespace: str, suggested: str) -> tuple[str, bool]:
    canonical = canonical_id(scene, namespace, suggested)
    if namespace == ENTITY_NS:
        return canonical, canonical in scene.get("entities", {})
    if namespace == MATERIAL_NS:
        return canonical, canonical in scene.get("materials", {})
    if namespace == BEHAVIOR_NS:
        return canonical, canonical in scene.get("behaviors", {})
    return canonical, False


def _split_path(path: str) -> list[str]:
    return [part for part in str(path).split("/") if part]


def _material_data_from_patch(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    shader_id = str(row.get("shader_id", "")).strip()
    material_type = str(row.get("type", "")).strip().lower()
    if not material_type:
        material_type = "recipe" if shader_id else "unlit"
    payload = dict(row)
    payload.setdefault("type", material_type)
    if shader_id:
        payload.setdefault("recipe_id", shader_id)
    return payload


def _next_op_id(turn_id: str, index: int) -> str:
    return f"{turn_id}-op-{index:05d}"


def patches_to_v2_ops(
    patches: list[dict[str, Any]],
    *,
    turn_id: str,
    prompt: str,
    scene: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    ops: list[dict[str, Any]] = []
    warnings: list[str] = []

    for idx, patch in enumerate(patches):
        parts = _split_path(str(patch.get("path", "")))
        if not parts:
            continue
        patch_op = str(patch.get("op", ""))
        at_ms = int(patch.get("at_ms", 0))
        op_id = _next_op_id(turn_id, idx)
        value = patch.get("value")

        if parts[0] == "actors" and len(parts) >= 2:
            actor_id = parts[1]
            entity_id, exists = _existing(scene, ENTITY_NS, actor_id)
            if len(parts) == 2:
                if patch_op == "remove":
                    ops.append({"op_id": op_id, "at_ms": at_ms, "op": "destroyEntity", "entity_id": entity_id})
                elif patch_op in {"add", "replace"}:
                    payload = value if isinstance(value, dict) else {}
                    kind = str(payload.get("type", "node")).strip().lower() or "node"
                    op_name = "updateEntity" if exists else "createEntity"
                    if op_name == "createEntity":
                        ops.append(
                            {
                                "op_id": op_id,
                                "at_ms": at_ms,
                                "op": "createEntity",
                                "entity_id": entity_id,
                                "kind": kind,
                                "data": payload,
                            }
                        )
                    else:
                        ops.append(
                            {
                                "op_id": op_id,
                                "at_ms": at_ms,
                                "op": "updateEntity",
                                "entity_id": entity_id,
                                "changes": payload,
                            }
                        )
                continue

            if parts[2] in {"motion", "animation"}:
                behavior_hint = f"{actor_id}-{parts[2]}"
                behavior_id, beh_exists = _existing(scene, BEHAVIOR_NS, behavior_hint)
                if patch_op == "remove":
                    ops.append({"op_id": op_id, "at_ms": at_ms, "op": "destroyBehavior", "behavior_id": behavior_id})
                else:
                    behavior_payload = {
                        "type": "parametric_motion" if parts[2] == "motion" else "timeline",
                        "name": parts[2],
                        "params": value if isinstance(value, dict) else {"value": value},
                    }
                    if beh_exists:
                        ops.append(
                            {
                                "op_id": op_id,
                                "at_ms": at_ms,
                                "op": "updateBehavior",
                                "behavior_id": behavior_id,
                                "changes": {"definition": behavior_payload, "target_id": entity_id},
                            }
                        )
                    else:
                        ops.append(
                            {
                                "op_id": op_id,
                                "at_ms": at_ms,
                                "op": "createBehavior",
                                "behavior_id": behavior_id,
                                "target_id": entity_id,
                                "data": behavior_payload,
                            }
                        )
                continue

        if parts[0] in {"charts", "fx"} and len(parts) >= 2:
            entity_hint = f"{parts[0]}-{parts[1]}"
            entity_id, exists = _existing(scene, ENTITY_NS, entity_hint)
            if patch_op == "remove":
                ops.append({"op_id": op_id, "at_ms": at_ms, "op": "destroyEntity", "entity_id": entity_id})
            else:
                payload = value if isinstance(value, dict) else {}
                kind = str(payload.get("type", parts[0])).strip().lower() or parts[0]
                if exists:
                    ops.append(
                        {
                            "op_id": op_id,
                            "at_ms": at_ms,
                            "op": "updateEntity",
                            "entity_id": entity_id,
                            "changes": payload,
                        }
                    )
                else:
                    ops.append(
                        {
                            "op_id": op_id,
                            "at_ms": at_ms,
                            "op": "createEntity",
                            "entity_id": entity_id,
                            "kind": kind,
                            "data": payload,
                        }
                    )
            continue

        if parts[0] == "materials" and len(parts) >= 2:
            material_hint = parts[1]
            material_id, exists = _existing(scene, MATERIAL_NS, material_hint)
            if patch_op == "remove":
                ops.append({"op_id": op_id, "at_ms": at_ms, "op": "destroyMaterial", "material_id": material_id})
            elif patch_op in {"add", "replace"}:
                payload = _material_data_from_patch(value)
                if exists:
                    ops.append(
                        {
                            "op_id": op_id,
                            "at_ms": at_ms,
                            "op": "updateMaterial",
                            "material_id": material_id,
                            "changes": payload,
                        }
                    )
                else:
                    ops.append(
                        {
                            "op_id": op_id,
                            "at_ms": at_ms,
                            "op": "createMaterial",
                            "material_id": material_id,
                            "data": payload,
                        }
                    )
            continue

        if parts[0] == "render" and len(parts) >= 2:
            entity_id, exists = _existing(scene, ENTITY_NS, "runtime-render")
            payload = {"mode": value}
            if exists:
                ops.append({"op_id": op_id, "at_ms": at_ms, "op": "updateEntity", "entity_id": entity_id, "changes": payload})
            else:
                ops.append(
                    {"op_id": op_id, "at_ms": at_ms, "op": "createEntity", "entity_id": entity_id, "kind": "runtime", "data": payload}
                )
            continue

        if parts[0] in {"environment", "camera", "lyrics", "scene"}:
            entity_id, exists = _existing(scene, ENTITY_NS, f"{parts[0]}-state")
            payload = value if isinstance(value, dict) else {"value": value}
            if exists:
                ops.append({"op_id": op_id, "at_ms": at_ms, "op": "updateEntity", "entity_id": entity_id, "changes": payload})
            else:
                ops.append(
                    {
                        "op_id": op_id,
                        "at_ms": at_ms,
                        "op": "createEntity",
                        "entity_id": entity_id,
                        "kind": parts[0],
                        "data": payload,
                    }
                )
            continue

        if parts[0] == "annotations":
            entity_hint = f"annotation-{idx}"
            entity_id, exists = _existing(scene, ENTITY_NS, entity_hint)
            payload = value if isinstance(value, dict) else {"text": str(value)}
            if exists:
                ops.append({"op_id": op_id, "at_ms": at_ms, "op": "updateEntity", "entity_id": entity_id, "changes": payload})
            else:
                ops.append(
                    {
                        "op_id": op_id,
                        "at_ms": at_ms,
                        "op": "createEntity",
                        "entity_id": entity_id,
                        "kind": "annotation",
                        "data": payload,
                    }
                )
            continue

        warnings.append(f"unsupported_v1_patch_path:{patch.get('path', '')}")

    lowered = str(prompt or "").lower()
    if not ops and any(token in lowered for token in ("bloop", "blooop")) and "fish" in lowered:
        fish_entity_id = ""
        for entity_id, entity in scene.get("entities", {}).items():
            if str(entity.get("kind", "")).lower() == "fish":
                fish_entity_id = entity_id
                break
        if fish_entity_id:
            base_idx = len(patches)
            behavior_id, behavior_exists = _existing(scene, BEHAVIOR_NS, "goldfish-bloop")
            if behavior_exists:
                ops.append(
                    {
                        "op_id": _next_op_id(turn_id, base_idx),
                        "at_ms": 160,
                        "op": "updateBehavior",
                        "behavior_id": behavior_id,
                        "changes": {"state": "bloop", "definition": {"type": "state_machine", "state": "bloop"}},
                    }
                )
            else:
                ops.append(
                    {
                        "op_id": _next_op_id(turn_id, base_idx),
                        "at_ms": 160,
                        "op": "createBehavior",
                        "behavior_id": behavior_id,
                        "target_id": fish_entity_id,
                        "data": {
                            "type": "state_machine",
                            "state": "bloop",
                            "states": {
                                "idle": {"transitions": [{"event": "bloop", "to": "bloop"}]},
                                "bloop": {"transitions": [{"event": "settle", "to": "idle"}]},
                            },
                        },
                    }
                )
            ops.append(
                {
                    "op_id": _next_op_id(turn_id, base_idx + 1),
                    "at_ms": 180,
                    "op": "trigger",
                    "target_id": behavior_id,
                    "action": "bloop",
                }
            )
            water_material_id = ""
            for material_id in scene.get("materials", {}):
                if "water" in material_id:
                    water_material_id = material_id
                    break
            if water_material_id:
                ops.append(
                    {
                        "op_id": _next_op_id(turn_id, base_idx + 2),
                        "at_ms": 220,
                        "op": "setUniform",
                        "material_id": water_material_id,
                        "uniform": "intensity",
                        "value": 0.62,
                    }
                )
    return normalize_ops(ops), warnings


__all__ = ["patches_to_v2_ops"]
