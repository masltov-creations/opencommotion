from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from typing import Any

from services.scene_v2.recipes import get_recipe, validate_uniform

ENTITY_NS = "entity"
MATERIAL_NS = "material"
BEHAVIOR_NS = "behavior"

THREE_D_KINDS = {"mesh", "camera", "light", "environment"}
BUILTIN_MATERIAL_TYPES = {"pbr", "unlit"}


@dataclass(frozen=True)
class SafetyPolicy:
    max_entities_2d: int
    max_entities_3d: int
    max_patch_ops_per_turn: int
    max_materials: int
    max_behaviors: int
    max_texture_dimension: int
    max_texture_memory_mb: int
    max_uniform_update_hz: float


@dataclass
class SceneApplyError(RuntimeError):
    code: str
    message: str
    detail: dict[str, Any]

    def __str__(self) -> str:
        return self.message


def _env_int(name: str, fallback: int, min_value: int = 1, max_value: int = 10_000) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return max(min_value, min(max_value, value))


def _env_float(name: str, fallback: float, min_value: float = 0.1, max_value: float = 1000.0) -> float:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return fallback
    try:
        value = float(raw)
    except ValueError:
        return fallback
    return max(min_value, min(max_value, value))


def default_policy() -> SafetyPolicy:
    return SafetyPolicy(
        max_entities_2d=_env_int("OPENCOMMOTION_V2_MAX_ENTITIES_2D", 400),
        max_entities_3d=_env_int("OPENCOMMOTION_V2_MAX_ENTITIES_3D", 250),
        max_patch_ops_per_turn=_env_int("OPENCOMMOTION_V2_MAX_PATCH_OPS_PER_TURN", 120),
        max_materials=_env_int("OPENCOMMOTION_V2_MAX_MATERIALS", 128),
        max_behaviors=_env_int("OPENCOMMOTION_V2_MAX_BEHAVIORS", 256),
        max_texture_dimension=_env_int("OPENCOMMOTION_V2_MAX_TEXTURE_DIMENSION", 2048),
        max_texture_memory_mb=_env_int("OPENCOMMOTION_V2_MAX_TEXTURE_MEMORY_MB", 128),
        max_uniform_update_hz=_env_float("OPENCOMMOTION_V2_MAX_UNIFORM_UPDATE_HZ", 30.0),
    )


def new_scene_state(scene_id: str) -> dict[str, Any]:
    return {
        "scene_id": str(scene_id),
        "revision": 0,
        "entities": {},
        "materials": {},
        "behaviors": {},
        "bindings": {"entity_to_material": {}},
        "applied_op_ids": [],
        "id_aliases": {},
        "counters": {ENTITY_NS: 1, MATERIAL_NS: 1, BEHAVIOR_NS: 1},
        "uniform_update_at": {},
        "trigger_log": [],
        "warnings": [],
    }


def scene_summary(scene: dict[str, Any]) -> dict[str, Any]:
    entities = scene.get("entities", {})
    materials = scene.get("materials", {})
    behaviors = scene.get("behaviors", {})
    return {
        "scene_id": scene.get("scene_id", ""),
        "revision": int(scene.get("revision", 0)),
        "entity_count": len(entities),
        "material_count": len(materials),
        "behavior_count": len(behaviors),
    }


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return cleaned or "item"


def _prefix(namespace: str) -> str:
    if namespace == ENTITY_NS:
        return "entity"
    if namespace == MATERIAL_NS:
        return "mat"
    if namespace == BEHAVIOR_NS:
        return "beh"
    return namespace


def _mint(scene: dict[str, Any], namespace: str, seed: str) -> str:
    counters = scene.setdefault("counters", {})
    idx = int(counters.get(namespace, 1))
    counters[namespace] = idx + 1
    return f"{_prefix(namespace)}:{_slug(seed)}#{idx:03d}"


def canonical_id(scene: dict[str, Any], namespace: str, raw_id: str | None) -> str:
    aliases: dict[str, str] = scene.setdefault("id_aliases", {})
    token = str(raw_id or "").strip()
    pref = _prefix(namespace)

    if token.startswith(f"{pref}:"):
        canonical = token
    elif token:
        alias_key = f"{namespace}:{token}"
        canonical = aliases.get(alias_key, "")
        if not canonical:
            canonical = _mint(scene, namespace, token)
            aliases[alias_key] = canonical
    else:
        canonical = _mint(scene, namespace, namespace)
    return canonical


def normalize_ops(ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: list[tuple[int, str, int, dict[str, Any]]] = []
    for idx, op in enumerate(ops):
        at_ms = int(op.get("at_ms", 0))
        op_id = str(op.get("op_id", f"op-{idx:05d}"))
        normalized = copy.deepcopy(op)
        normalized["at_ms"] = max(0, at_ms)
        normalized["op_id"] = op_id
        indexed.append((normalized["at_ms"], op_id, idx, normalized))
    indexed.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in indexed]


def _looks_like_rebuild(scene: dict[str, Any], ops: list[dict[str, Any]]) -> bool:
    existing = len(scene.get("entities", {}))
    if existing <= 0:
        return False
    creates = sum(1 for op in ops if op.get("op") == "createEntity")
    destroys = sum(1 for op in ops if op.get("op") == "destroyEntity")
    churn = creates + destroys
    return destroys >= 3 and creates >= 3 and churn > max(8, int(existing * 0.4))


def _entity_counts(scene: dict[str, Any]) -> tuple[int, int]:
    entities = scene.get("entities", {})
    three_d = 0
    two_d = 0
    for row in entities.values():
        kind = str((row or {}).get("kind", "")).strip().lower()
        if kind in THREE_D_KINDS:
            three_d += 1
        else:
            two_d += 1
    return two_d, three_d


def _enforce_caps(scene: dict[str, Any], policy: SafetyPolicy) -> None:
    two_d_count, three_d_count = _entity_counts(scene)
    if two_d_count > policy.max_entities_2d:
        raise SceneApplyError(
            code="patch_budget_exceeded",
            message="2D entity cap exceeded",
            detail={"cap": policy.max_entities_2d, "count": two_d_count, "scope": "entities_2d"},
        )
    if three_d_count > policy.max_entities_3d:
        raise SceneApplyError(
            code="patch_budget_exceeded",
            message="3D entity cap exceeded",
            detail={"cap": policy.max_entities_3d, "count": three_d_count, "scope": "entities_3d"},
        )
    materials = scene.get("materials", {})
    if len(materials) > policy.max_materials:
        raise SceneApplyError(
            code="patch_budget_exceeded",
            message="material cap exceeded",
            detail={"cap": policy.max_materials, "count": len(materials), "scope": "materials"},
        )
    behaviors = scene.get("behaviors", {})
    if len(behaviors) > policy.max_behaviors:
        raise SceneApplyError(
            code="patch_budget_exceeded",
            message="behavior cap exceeded",
            detail={"cap": policy.max_behaviors, "count": len(behaviors), "scope": "behaviors"},
        )


def _resolve_transition(scene: dict[str, Any], behavior_id: str, action: str) -> str | None:
    behavior = scene.get("behaviors", {}).get(behavior_id, {})
    definition = behavior.get("definition", {})
    states = definition.get("states", {})
    current = str(behavior.get("state") or definition.get("state") or "idle")
    transitions = (((states.get(current) or {}).get("transitions")) if isinstance(states, dict) else None) or []
    if not isinstance(transitions, list):
        return None
    for row in transitions:
        if not isinstance(row, dict):
            continue
        if str(row.get("event", "")).strip() == action:
            nxt = str(row.get("to", "")).strip()
            return nxt or None
    return None


def _apply_uniform_update(
    scene: dict[str, Any],
    op: dict[str, Any],
    policy: SafetyPolicy,
) -> None:
    materials = scene.setdefault("materials", {})
    material_id = canonical_id(scene, MATERIAL_NS, op.get("material_id"))
    material = materials.get(material_id)
    if material is None:
        raise SceneApplyError(
            code="unknown_material_id",
            message=f"material '{material_id}' was not found",
            detail={"material_id": material_id},
        )

    uniform_name = str(op.get("uniform", "")).strip()
    if not uniform_name:
        raise SceneApplyError(
            code="uniform_name_required",
            message="uniform name is required",
            detail={"material_id": material_id},
        )

    at_ms = int(op.get("at_ms", 0))
    last_updates = scene.setdefault("uniform_update_at", {})
    key = f"{material_id}:{uniform_name}"
    previous_ms = int(last_updates.get(key, -1))

    max_hz = policy.max_uniform_update_hz
    recipe_id = str(material.get("recipe_id", "")).strip()
    recipe = get_recipe(recipe_id) if recipe_id else None
    if recipe and uniform_name in recipe.uniform_schema:
        max_hz = min(max_hz, recipe.uniform_schema[uniform_name].max_update_hz)
    if max_hz <= 0:
        max_hz = policy.max_uniform_update_hz

    min_delta_ms = int(round(1000.0 / max_hz))
    if previous_ms >= 0 and (at_ms - previous_ms) < min_delta_ms:
        raise SceneApplyError(
            code="uniform_rate_limited",
            message=f"uniform '{uniform_name}' update frequency exceeds {max_hz:.2f}Hz",
            detail={"material_id": material_id, "uniform": uniform_name, "max_hz": max_hz},
        )

    raw_value = op.get("value")
    if recipe_id:
        ok, reason, numeric = validate_uniform(recipe_id, uniform_name, raw_value)
        if not ok:
            raise SceneApplyError(
                code=reason or "uniform_validation_failed",
                message=f"uniform '{uniform_name}' rejected for recipe '{recipe_id}'",
                detail={"material_id": material_id, "uniform": uniform_name, "recipe_id": recipe_id},
            )
        value = numeric
    else:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise SceneApplyError(
                code="uniform_not_numeric",
                message=f"uniform '{uniform_name}' must be numeric",
                detail={"material_id": material_id, "uniform": uniform_name},
            ) from None

    uniforms = material.setdefault("uniforms", {})
    uniforms[uniform_name] = value
    material["updated_at_ms"] = at_ms
    last_updates[key] = at_ms


def _apply_single_op(scene: dict[str, Any], op: dict[str, Any], policy: SafetyPolicy) -> None:
    entities = scene.setdefault("entities", {})
    materials = scene.setdefault("materials", {})
    behaviors = scene.setdefault("behaviors", {})
    bindings = scene.setdefault("bindings", {}).setdefault("entity_to_material", {})

    op_name = str(op.get("op", ""))
    at_ms = int(op.get("at_ms", 0))

    if op_name == "createEntity":
        entity_id = canonical_id(scene, ENTITY_NS, op.get("entity_id"))
        data = copy.deepcopy(op.get("data") or {})
        kind = str(op.get("kind", "")).strip().lower()
        if not kind:
            raise SceneApplyError(code="unknown_entity_kind", message="entity kind is required", detail={"entity_id": entity_id})
        existing = entities.get(entity_id, {})
        entities[entity_id] = {**existing, **data, "id": entity_id, "kind": kind, "updated_at_ms": at_ms}
        return

    if op_name == "updateEntity":
        entity_id = canonical_id(scene, ENTITY_NS, op.get("entity_id"))
        if entity_id not in entities:
            raise SceneApplyError(
                code="unknown_entity_id",
                message=f"entity '{entity_id}' was not found",
                detail={"entity_id": entity_id},
            )
        changes = copy.deepcopy(op.get("changes") or {})
        entities[entity_id] = {**entities[entity_id], **changes, "updated_at_ms": at_ms}
        return

    if op_name == "destroyEntity":
        entity_id = canonical_id(scene, ENTITY_NS, op.get("entity_id"))
        entities.pop(entity_id, None)
        bindings.pop(entity_id, None)
        return

    if op_name == "createMaterial":
        material_id = canonical_id(scene, MATERIAL_NS, op.get("material_id"))
        data = copy.deepcopy(op.get("data") or {})
        material_type = str(data.get("type", "unlit")).strip().lower() or "unlit"
        recipe_id = str(data.get("recipe_id") or data.get("shader_id") or "").strip()
        if material_type not in BUILTIN_MATERIAL_TYPES and not recipe_id:
            raise SceneApplyError(
                code="unknown_recipe_id",
                message=f"material '{material_id}' requires recipe_id for non-built-in type",
                detail={"material_id": material_id},
            )
        if recipe_id and get_recipe(recipe_id) is None:
            raise SceneApplyError(
                code="unknown_recipe_id",
                message=f"recipe '{recipe_id}' is not available",
                detail={"material_id": material_id, "recipe_id": recipe_id},
            )
        materials[material_id] = {
            **materials.get(material_id, {}),
            **data,
            "id": material_id,
            "type": material_type,
            "recipe_id": recipe_id or "",
            "uniforms": copy.deepcopy(data.get("uniforms") or {}),
            "updated_at_ms": at_ms,
        }
        return

    if op_name == "updateMaterial":
        material_id = canonical_id(scene, MATERIAL_NS, op.get("material_id"))
        if material_id not in materials:
            raise SceneApplyError(
                code="unknown_material_id",
                message=f"material '{material_id}' was not found",
                detail={"material_id": material_id},
            )
        changes = copy.deepcopy(op.get("changes") or {})
        if "recipe_id" in changes:
            recipe_id = str(changes.get("recipe_id") or "").strip()
            if recipe_id and get_recipe(recipe_id) is None:
                raise SceneApplyError(
                    code="unknown_recipe_id",
                    message=f"recipe '{recipe_id}' is not available",
                    detail={"material_id": material_id, "recipe_id": recipe_id},
                )
        materials[material_id] = {**materials[material_id], **changes, "updated_at_ms": at_ms}
        return

    if op_name == "destroyMaterial":
        material_id = canonical_id(scene, MATERIAL_NS, op.get("material_id"))
        materials.pop(material_id, None)
        for key, value in list(bindings.items()):
            if value == material_id:
                bindings.pop(key, None)
        return

    if op_name == "applyMaterial":
        entity_id = canonical_id(scene, ENTITY_NS, op.get("entity_id"))
        material_id = canonical_id(scene, MATERIAL_NS, op.get("material_id"))
        if entity_id not in entities:
            raise SceneApplyError(
                code="unknown_entity_id",
                message=f"entity '{entity_id}' was not found",
                detail={"entity_id": entity_id},
            )
        if material_id not in materials:
            raise SceneApplyError(
                code="unknown_material_id",
                message=f"material '{material_id}' was not found",
                detail={"material_id": material_id},
            )
        bindings[entity_id] = material_id
        return

    if op_name == "setUniform":
        _apply_uniform_update(scene, op, policy)
        return

    if op_name == "createBehavior":
        behavior_id = canonical_id(scene, BEHAVIOR_NS, op.get("behavior_id"))
        target_id = canonical_id(scene, ENTITY_NS, op.get("target_id"))
        if target_id not in entities:
            raise SceneApplyError(
                code="unknown_entity_id",
                message=f"behavior target '{target_id}' was not found",
                detail={"target_id": target_id},
            )
        data = copy.deepcopy(op.get("data") or {})
        behaviors[behavior_id] = {
            **behaviors.get(behavior_id, {}),
            "id": behavior_id,
            "target_id": target_id,
            "definition": data,
            "state": str(data.get("state", "idle")),
            "updated_at_ms": at_ms,
        }
        return

    if op_name == "updateBehavior":
        behavior_id = canonical_id(scene, BEHAVIOR_NS, op.get("behavior_id"))
        if behavior_id not in behaviors:
            raise SceneApplyError(
                code="unknown_behavior_id",
                message=f"behavior '{behavior_id}' was not found",
                detail={"behavior_id": behavior_id},
            )
        changes = copy.deepcopy(op.get("changes") or {})
        behavior = {**behaviors[behavior_id], **changes, "updated_at_ms": at_ms}
        if "definition" in changes and isinstance(changes["definition"], dict):
            behavior["definition"] = {**behaviors[behavior_id].get("definition", {}), **changes["definition"]}
        behaviors[behavior_id] = behavior
        return

    if op_name == "destroyBehavior":
        behavior_id = canonical_id(scene, BEHAVIOR_NS, op.get("behavior_id"))
        behaviors.pop(behavior_id, None)
        return

    if op_name == "trigger":
        target_id = str(op.get("target_id", "")).strip()
        action = str(op.get("action", "")).strip()
        if not target_id or not action:
            raise SceneApplyError(
                code="invalid_trigger",
                message="trigger requires target_id and action",
                detail={"target_id": target_id, "action": action},
            )
        canonical_behavior_id = canonical_id(scene, BEHAVIOR_NS, target_id)
        if canonical_behavior_id in behaviors:
            behaviors[canonical_behavior_id]["last_trigger"] = action
            nxt = _resolve_transition(scene, canonical_behavior_id, action)
            if nxt:
                behaviors[canonical_behavior_id]["state"] = nxt
        else:
            canonical_entity_id = canonical_id(scene, ENTITY_NS, target_id)
            if canonical_entity_id in entities:
                entities[canonical_entity_id]["last_trigger"] = action
            else:
                raise SceneApplyError(
                    code="unknown_trigger_target",
                    message=f"trigger target '{target_id}' was not found",
                    detail={"target_id": target_id},
                )
        trigger_log = scene.setdefault("trigger_log", [])
        trigger_log.append({"target_id": target_id, "action": action, "at_ms": at_ms})
        if len(trigger_log) > 200:
            del trigger_log[:-200]
        return

    raise SceneApplyError(
        code="unsupported_op",
        message=f"unsupported v2 patch op '{op_name}'",
        detail={"op": op_name},
    )


def apply_ops(
    scene: dict[str, Any],
    ops: list[dict[str, Any]],
    policy: SafetyPolicy,
    *,
    explicit_rebuild: bool = False,
) -> dict[str, Any]:
    if len(ops) > policy.max_patch_ops_per_turn:
        raise SceneApplyError(
            code="patch_budget_exceeded",
            message="patch op count exceeds cap",
            detail={"cap": policy.max_patch_ops_per_turn, "count": len(ops), "scope": "ops_per_turn"},
        )

    normalized = normalize_ops(ops)
    if _looks_like_rebuild(scene, normalized) and not explicit_rebuild:
        raise SceneApplyError(
            code="suspicious_rebuild",
            message="follow-up patch set looks like a scene rebuild",
            detail={"hint": "set intent.rebuild=true for explicit rebuild turns"},
        )

    warnings: list[str] = []
    applied: list[dict[str, Any]] = []
    seen = set(str(item) for item in scene.get("applied_op_ids", []))

    for op in normalized:
        op_id = str(op.get("op_id", "")).strip()
        if not op_id:
            continue
        if op_id in seen:
            warnings.append(f"op_duplicate_ignored:{op_id}")
            continue
        _apply_single_op(scene, op, policy)
        seen.add(op_id)
        applied.append(op)

    _enforce_caps(scene, policy)

    scene["applied_op_ids"] = sorted(seen)
    scene["revision"] = int(scene.get("revision", 0)) + 1
    if warnings:
        history = scene.setdefault("warnings", [])
        history.extend(warnings)
        if len(history) > 200:
            del history[:-200]

    return {"applied_ops": applied, "warnings": warnings, "degrade_notes": []}


__all__ = [
    "BEHAVIOR_NS",
    "ENTITY_NS",
    "MATERIAL_NS",
    "SafetyPolicy",
    "SceneApplyError",
    "apply_ops",
    "canonical_id",
    "default_policy",
    "new_scene_state",
    "normalize_ops",
    "scene_summary",
]
