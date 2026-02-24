from services.brush_engine.opencommotion_brush.compiler import compile_brush_batch


def test_compile_spawns_character() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "s1",
                "kind": "spawnCharacter",
                "params": {"actor_id": "guide"},
                "timing": {"start_ms": 0, "duration_ms": 100, "easing": "linear"},
            }
        ]
    )
    assert patches
    assert patches[0]["path"] == "/actors/guide"


def test_unknown_kind_generates_warning_patch() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "s2",
                "kind": "bad-kind",
                "params": {},
                "timing": {"start_ms": 0, "duration_ms": 50, "easing": "linear"},
            }
        ]
    )
    assert "Unsupported stroke kind" in patches[0]["value"]["text"]
