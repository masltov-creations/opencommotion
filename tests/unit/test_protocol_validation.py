from services.protocol import ProtocolValidationError, ProtocolValidator


def test_protocol_validator_accepts_valid_brush_stroke() -> None:
    validator = ProtocolValidator()
    validator.validate(
        "types/brush_stroke_v1.schema.json",
        {
            "stroke_id": "s1",
            "kind": "spawnCharacter",
            "params": {"actor_id": "guide"},
            "timing": {"start_ms": 0, "duration_ms": 200, "easing": "linear"},
        },
    )


def test_protocol_validator_rejects_bad_brush_kind() -> None:
    validator = ProtocolValidator()
    try:
        validator.validate(
            "types/brush_stroke_v1.schema.json",
            {
                "stroke_id": "s1",
                "kind": "not-a-kind",
                "params": {},
                "timing": {"start_ms": 0, "duration_ms": 200, "easing": "linear"},
            },
        )
    except ProtocolValidationError as exc:
        assert exc.issues
        assert "kind" in exc.issues[0]["path"] or "is not one of" in exc.issues[0]["message"]
        return
    raise AssertionError("Expected ProtocolValidationError for invalid brush kind")


def test_protocol_validator_resolves_refs_for_event_schema() -> None:
    validator = ProtocolValidator()
    validator.validate(
        "events/agent_visual_brush_stroke.schema.json",
        {
            "event_type": "agent.visual.brush.stroke",
            "session_id": "sess-1",
            "turn_id": "turn-1",
            "timestamp": "2026-02-24T00:00:00Z",
            "actor": "visual",
            "payload": {
                "stroke_id": "s1",
                "kind": "spawnCharacter",
                "params": {"actor_id": "guide"},
                "timing": {"start_ms": 0, "duration_ms": 200, "easing": "linear"},
            },
        },
    )


def test_protocol_validator_accepts_runtime_capabilities_v2_with_recipe_refs() -> None:
    validator = ProtocolValidator()
    validator.validate(
        "types/runtime_capabilities_v2.schema.json",
        {
            "version": "v2",
            "renderers": ["three-webgl"],
            "features": {
                "shaderRecipes": True,
                "gltfImport": False,
                "pbr": True,
                "particles": True,
                "physics": False,
            },
            "limits": {
                "max_entities_2d": 400,
                "max_entities_3d": 250,
                "max_patch_ops_per_turn": 120,
                "max_materials": 128,
                "max_behaviors": 256,
                "max_texture_dimension": 2048,
                "max_texture_memory_mb": 128,
                "max_uniform_update_hz": 30,
            },
            "shader_recipes": [
                {
                    "recipe_id": "water_volume_tint",
                    "version": "1.0.0",
                    "backend_targets": ["three-webgl"],
                    "uniform_schema": {
                        "density": {"type": "number", "default": 0.36, "min": 0.0, "max": 1.0, "max_update_hz": 30.0}
                    },
                    "texture_slots": [],
                }
            ],
        },
    )
