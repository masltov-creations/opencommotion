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


def test_compile_fish_scene_primitives() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "render-mode",
                "kind": "setRenderMode",
                "params": {"mode": "3d"},
                "timing": {"start_ms": 0, "duration_ms": 100, "easing": "linear"},
            },
            {
                "stroke_id": "spawn-fish",
                "kind": "spawnSceneActor",
                "params": {"actor_id": "goldfish", "actor_type": "fish", "x": 300, "y": 210},
                "timing": {"start_ms": 30, "duration_ms": 100, "easing": "linear"},
            },
            {
                "stroke_id": "fx-bubble",
                "kind": "emitFx",
                "params": {"fx_id": "bubble_emitter", "seed": 11, "count": 6},
                "timing": {"start_ms": 60, "duration_ms": 500, "easing": "linear"},
            },
        ]
    )
    assert any(p["path"] == "/render/mode" and p["value"] == "3d" for p in patches)
    assert any(p["path"] == "/actors/goldfish" and p["value"]["type"] == "fish" for p in patches)
    bubble_patch = next(p for p in patches if p["path"] == "/fx/bubble_emitter")
    assert bubble_patch["value"]["type"] == "bubble_emitter"
    assert len(bubble_patch["value"]["particles"]) == 6


def test_compile_shader_validation_fallback() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "mat-bad",
                "kind": "applyMaterialFx",
                "params": {
                    "material_id": "fish_bowl_glass",
                    "shader_id": "glass_refraction_like",
                    "uniforms": {"ior": 9.0},
                },
                "timing": {"start_ms": 100, "duration_ms": 100, "easing": "linear"},
            }
        ]
    )
    material = next(p for p in patches if p["path"] == "/materials/fish_bowl_glass")
    assert material["value"]["fallback"] is True
    assert "reason" in material["value"]
    warning = next(p for p in patches if p["path"] == "/annotations/-")
    assert "Material fallback" in warning["value"]["text"]


def test_compile_market_growth_chart_hardening() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "line-growth",
                "kind": "drawAdoptionCurve",
                "params": {
                    "trend": "growth",
                    "points": [[100, 20], [0, 92], [60, 80], [40, 86]],
                },
                "timing": {"start_ms": 200, "duration_ms": 1400, "easing": "linear"},
            },
            {
                "stroke_id": "pie-growth",
                "kind": "drawPieSaturation",
                "params": {
                    "slices": [
                        {"label": "Core", "value": 4},
                        {"label": "Attach", "value": 4},
                        {"label": "Expansion", "value": 2},
                    ]
                },
                "timing": {"start_ms": 300, "duration_ms": 1200, "easing": "linear"},
            },
            {
                "stroke_id": "attach-bars",
                "kind": "drawSegmentedAttachBars",
                "params": {
                    "segments": [
                        {"label": "Enterprise", "target": 120, "color": "#22d3ee"},
                        {"label": "SMB", "target": -8, "color": "#f59e0b"},
                    ]
                },
                "timing": {"start_ms": 500, "duration_ms": 1800, "easing": "linear"},
            },
        ]
    )
    line = next(p for p in patches if p["path"] == "/charts/adoption_curve")["value"]
    assert line["points"][0][0] == 0.0
    assert line["points"][-1][0] == 100.0
    assert all(line["points"][idx + 1][1] <= line["points"][idx][1] for idx in range(len(line["points"]) - 1))
    assert line["duration_ms"] == 1400

    pie = next(p for p in patches if p["path"] == "/charts/saturation_pie")["value"]
    assert sum(int(row["value"]) for row in pie["slices"]) == 100

    segmented = next(p for p in patches if p["path"] == "/charts/segmented_attach")["value"]
    assert segmented["segments"][0]["target"] == 100.0
    assert segmented["segments"][1]["target"] == 0.0


def test_compile_lyrics_track_generates_words_path() -> None:
    patches = compile_brush_batch(
        [
            {
                "stroke_id": "lyrics",
                "kind": "setLyricsTrack",
                "params": {"words": ["The", "cow", "jumps"], "start_ms": 300, "step_ms": 250},
                "timing": {"start_ms": 280, "duration_ms": 1200, "easing": "linear"},
            }
        ]
    )
    lyric_patch = next(p for p in patches if p["path"] == "/lyrics/words")
    assert lyric_patch["value"]["items"][0]["text"] == "The"
    assert lyric_patch["value"]["items"][1]["at_ms"] == 550
