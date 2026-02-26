from __future__ import annotations

from services.scene_v2.engine import SceneApplyError, apply_ops, default_policy, new_scene_state, normalize_ops


def test_normalize_ops_orders_by_at_ms_then_op_id_then_ingress() -> None:
    ops = [
        {"op_id": "b", "at_ms": 100, "op": "destroyEntity", "entity_id": "entity:alpha#001"},
        {"op_id": "a", "at_ms": 100, "op": "destroyEntity", "entity_id": "entity:alpha#001"},
        {"op_id": "c", "at_ms": 40, "op": "destroyEntity", "entity_id": "entity:alpha#001"},
    ]
    normalized = normalize_ops(ops)
    assert [row["op_id"] for row in normalized] == ["c", "a", "b"]


def test_apply_ops_scene_lifetime_dedupes_duplicate_op_id() -> None:
    policy = default_policy()
    scene = new_scene_state("scene-dedupe")
    create_ops = [
        {
            "op_id": "turn-1-op-1",
            "at_ms": 0,
            "op": "createEntity",
            "entity_id": "fish",
            "kind": "fish",
            "data": {"x": 10, "y": 20},
        }
    ]
    apply_ops(scene, create_ops, policy, explicit_rebuild=False)
    assert len(scene["entities"]) == 1

    duplicate = [
        {
            "op_id": "turn-1-op-1",
            "at_ms": 100,
            "op": "updateEntity",
            "entity_id": "fish",
            "changes": {"x": 30},
        }
    ]
    result = apply_ops(scene, duplicate, policy, explicit_rebuild=False)
    assert result["applied_ops"] == []
    assert any("op_duplicate_ignored" in warning for warning in result["warnings"])
    entity = next(iter(scene["entities"].values()))
    assert entity["x"] == 10


def test_apply_ops_rejects_suspicious_rebuild_without_intent() -> None:
    policy = default_policy()
    scene = new_scene_state("scene-rebuild")
    first_turn = []
    for idx in range(14):
        first_turn.append(
            {
                "op_id": f"seed-op-{idx:03d}",
                "at_ms": idx,
                "op": "createEntity",
                "entity_id": f"entity-{idx}",
                "kind": "shape",
                "data": {"x": idx * 3, "y": idx * 2},
            }
        )
    apply_ops(scene, first_turn, policy, explicit_rebuild=False)
    assert len(scene["entities"]) >= 10

    rebuild_ops = []
    for idx in range(7):
        rebuild_ops.append(
            {
                "op_id": f"rebuild-destroy-{idx:03d}",
                "at_ms": idx,
                "op": "destroyEntity",
                "entity_id": f"entity-{idx}",
            }
        )
    for idx in range(7):
        rebuild_ops.append(
            {
                "op_id": f"rebuild-create-{idx:03d}",
                "at_ms": idx + 20,
                "op": "createEntity",
                "entity_id": f"replacement-{idx}",
                "kind": "shape",
                "data": {"x": 100 + idx, "y": 120 + idx},
            }
        )

    try:
        apply_ops(scene, rebuild_ops, policy, explicit_rebuild=False)
    except SceneApplyError as exc:
        assert exc.code == "suspicious_rebuild"
        return
    raise AssertionError("Expected suspicious_rebuild rejection")


def test_set_uniform_rejects_out_of_range_recipe_value() -> None:
    policy = default_policy()
    scene = new_scene_state("scene-uniform")
    apply_ops(
        scene,
        [
            {
                "op_id": "mat-1",
                "at_ms": 0,
                "op": "createMaterial",
                "material_id": "water",
                "data": {"type": "recipe", "recipe_id": "water_volume_tint"},
            }
        ],
        policy,
        explicit_rebuild=False,
    )
    try:
        apply_ops(
            scene,
            [
                {
                    "op_id": "uniform-1",
                    "at_ms": 120,
                    "op": "setUniform",
                    "material_id": "water",
                    "uniform": "density",
                    "value": 2.4,
                }
            ],
            policy,
            explicit_rebuild=False,
        )
    except SceneApplyError as exc:
        assert exc.code == "uniform_out_of_range"
        return
    raise AssertionError("Expected uniform_out_of_range rejection")
