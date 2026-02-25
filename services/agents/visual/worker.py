from __future__ import annotations


def _wants_fish_scene(prompt: str) -> bool:
    keys = ("fish bowl", "fishbowl", "goldfish", "fish swimming", "bubbles", "caustic", "aquarium")
    return any(k in prompt for k in keys)


def _render_mode(prompt: str) -> str:
    if "3d" in prompt or "three-dimensional" in prompt or "refraction" in prompt or "volumetric" in prompt:
        return "3d"
    if "2d" in prompt or "stylized layers" in prompt or "parallax" in prompt:
        return "2d"
    return "2d"


def _wants_market_growth_scene(prompt: str) -> bool:
    keys = ("market growth", "segmented attach", "attach", "presentation", "graph", "increase", "timeline")
    hits = sum(1 for k in keys if k in prompt)
    return hits >= 2


def _wants_day_night_scene(prompt: str) -> bool:
    p = prompt
    if "day-to-night" in p or "day to night" in p:
        return True
    return "day" in p and "night" in p


def _wants_cow_moon_lyric_scene(prompt: str) -> bool:
    p = prompt
    has_cow_moon = "cow" in p and "moon" in p
    has_lyric_intent = any(key in p for key in ("lyric", "lyrics", "bouncing ball", "phrase", "word"))
    return has_cow_moon and has_lyric_intent


def generate_visual_strokes(prompt: str) -> list[dict]:
    p = prompt.lower()
    market_growth_scene = _wants_market_growth_scene(p)
    day_night_scene = _wants_day_night_scene(p)
    cow_moon_lyric_scene = _wants_cow_moon_lyric_scene(p)
    mode = _render_mode(p)
    strokes: list[dict] = [
        {
            "stroke_id": "spawn-guide",
            "kind": "spawnCharacter",
            "params": {"actor_id": "guide", "x": 180, "y": 190},
            "timing": {"start_ms": 0, "duration_ms": 200, "easing": "easeOutCubic"},
        }
    ]

    if "moonwalk" in p:
        strokes.append(
            {
                "stroke_id": "moonwalk-guide",
                "kind": "animateMoonwalk",
                "params": {"actor_id": "guide"},
                "timing": {"start_ms": 250, "duration_ms": 1300, "easing": "easeInOutCubic"},
            }
        )

    if "globe" in p or "ufo" in p:
        strokes.extend(
            [
                {
                    "stroke_id": "orbit-globe",
                    "kind": "orbitGlobe",
                    "params": {"radius": 82},
                    "timing": {"start_ms": 300, "duration_ms": 1200, "easing": "linear"},
                },
                {
                    "stroke_id": "ufo-landing",
                    "kind": "ufoLandingBeat",
                    "params": {},
                    "timing": {"start_ms": 1400, "duration_ms": 1000, "easing": "easeInQuart"},
                },
            ]
        )

    if "chart" in p or "adoption" in p or "pie" in p or market_growth_scene:
        line_params = {}
        pie_params = {}
        if market_growth_scene:
            line_params = {
                "trend": "growth",
                "series": "market_growth",
                "points": [[0, 90], [20, 82], [40, 70], [60, 54], [80, 37], [100, 22]],
            }
            pie_params = {
                "slices": [
                    {"label": "Core", "value": 42},
                    {"label": "Expansion", "value": 33},
                    {"label": "Attach", "value": 25},
                ]
            }
        strokes.extend(
            [
                {
                    "stroke_id": "chart-line",
                    "kind": "drawAdoptionCurve",
                    "params": line_params,
                    "timing": {"start_ms": 200, "duration_ms": 1500 if market_growth_scene else 900, "easing": "easeOutQuart"},
                },
                {
                    "stroke_id": "chart-pie",
                    "kind": "drawPieSaturation",
                    "params": pie_params,
                    "timing": {"start_ms": 1100, "duration_ms": 1200 if market_growth_scene else 800, "easing": "easeOutCubic"},
                },
            ]
        )

    if market_growth_scene:
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode-market",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 120, "easing": "linear"},
                },
                {
                    "stroke_id": "segmented-attach-bars",
                    "kind": "drawSegmentedAttachBars",
                    "params": {
                        "segments": [
                            {"label": "Enterprise", "target": 84, "color": "#22d3ee"},
                            {"label": "Mid-Market", "target": 67, "color": "#34d399"},
                            {"label": "SMB", "target": 56, "color": "#f59e0b"},
                        ],
                        "trend": "growth",
                    },
                    "timing": {"start_ms": 700, "duration_ms": 2200, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "camera-market",
                    "kind": "setCameraMove",
                    "params": {"mode": "presentation-pan", "stabilized": True, "speed": 0.2},
                    "timing": {"start_ms": 200, "duration_ms": 2600, "easing": "easeInOutSine"},
                },
                {
                    "stroke_id": "market-note",
                    "kind": "annotateInsight",
                    "params": {"text": "Market growth and segmented attach are increasing over time."},
                    "timing": {"start_ms": 1800, "duration_ms": 200, "easing": "linear"},
                },
            ]
        )

    if day_night_scene:
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode-day-night",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 100, "easing": "linear"},
                },
                {
                    "stroke_id": "day-mood",
                    "kind": "setEnvironmentMood",
                    "params": {"mood": {"phase": "day", "lighting": "bright", "sky": "clear"}},
                    "timing": {"start_ms": 0, "duration_ms": 1200, "easing": "easeInOutSine"},
                },
                {
                    "stroke_id": "day-night-transition",
                    "kind": "sceneMorph",
                    "params": {},
                    "timing": {"start_ms": 900, "duration_ms": 2200, "easing": "easeInOutCubic"},
                },
                {
                    "stroke_id": "night-mood",
                    "kind": "setEnvironmentMood",
                    "params": {"mood": {"phase": "night", "lighting": "soft", "sky": "stars"}},
                    "timing": {"start_ms": 2600, "duration_ms": 1300, "easing": "easeInOutCubic"},
                },
            ]
        )

    if cow_moon_lyric_scene:
        words = ["The", "cow", "jumps", "over", "the", "moon"]
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode-cow-moon",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 100, "easing": "linear"},
                },
                {
                    "stroke_id": "spawn-cow",
                    "kind": "spawnSceneActor",
                    "params": {"actor_id": "cow", "actor_type": "cow", "x": 230, "y": 260},
                    "timing": {"start_ms": 80, "duration_ms": 260, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "spawn-moon",
                    "kind": "spawnSceneActor",
                    "params": {"actor_id": "moon", "actor_type": "moon", "x": 520, "y": 110},
                    "timing": {"start_ms": 120, "duration_ms": 220, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "cow-jump",
                    "kind": "setActorMotion",
                    "params": {
                        "actor_id": "cow",
                        "motion": {
                            "name": "jump-arc",
                            "loop": False,
                            "path_points": [[230, 260], [320, 180], [430, 150], [520, 210]],
                            "duration_ms": 2600,
                        },
                    },
                    "timing": {"start_ms": 380, "duration_ms": 2600, "easing": "easeInOutCubic"},
                },
                {
                    "stroke_id": "lyrics-track",
                    "kind": "setLyricsTrack",
                    "params": {"words": words, "start_ms": 450, "step_ms": 420},
                    "timing": {"start_ms": 430, "duration_ms": 2600, "easing": "linear"},
                },
                {
                    "stroke_id": "fx-bounce-ball",
                    "kind": "emitFx",
                    "params": {"fx_id": "bouncing_ball", "start_ms": 450, "step_ms": 420, "words_count": len(words)},
                    "timing": {"start_ms": 430, "duration_ms": 2600, "easing": "linear"},
                },
            ]
        )

    if _wants_fish_scene(p):
        mode = _render_mode(p)
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 120, "easing": "linear"},
                },
                {
                    "stroke_id": "spawn-bowl",
                    "kind": "spawnSceneActor",
                    "params": {
                        "actor_id": "fish_bowl",
                        "actor_type": "bowl",
                        "x": 330,
                        "y": 205,
                        "style": {"glass": "clear", "desk_anchor": True},
                    },
                    "timing": {"start_ms": 40, "duration_ms": 240, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "spawn-fish",
                    "kind": "spawnSceneActor",
                    "params": {
                        "actor_id": "goldfish",
                        "actor_type": "fish",
                        "x": 310,
                        "y": 205,
                        "style": {"species": "goldfish", "palette": "warm"},
                    },
                    "timing": {"start_ms": 120, "duration_ms": 260, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "spawn-plant",
                    "kind": "spawnSceneActor",
                    "params": {"actor_id": "plant_a", "actor_type": "plant", "x": 355, "y": 238},
                    "timing": {"start_ms": 130, "duration_ms": 220, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "fish-swim",
                    "kind": "setActorMotion",
                    "params": {
                        "actor_id": "goldfish",
                        "motion": {
                            "name": "swim-cycle",
                            "loop": True,
                            "path_points": [[280, 210], [322, 182], [380, 205], [338, 234]],
                            "seed": 41,
                        },
                    },
                    "timing": {"start_ms": 260, "duration_ms": 4200, "easing": "easeInOutSine"},
                },
                {
                    "stroke_id": "plant-sway",
                    "kind": "setActorAnimation",
                    "params": {
                        "actor_id": "plant_a",
                        "animation": {"name": "sway", "amplitude": 10, "loop": True},
                    },
                    "timing": {"start_ms": 320, "duration_ms": 4200, "easing": "easeInOutSine"},
                },
                {
                    "stroke_id": "fx-bubbles",
                    "kind": "emitFx",
                    "params": {"fx_id": "bubble_emitter", "seed": 42, "count": 22},
                    "timing": {"start_ms": 460, "duration_ms": 3800, "easing": "linear"},
                },
                {
                    "stroke_id": "fx-caustic",
                    "kind": "emitFx",
                    "params": {"fx_id": "caustic_pattern", "intensity": 0.42, "shimmer_period_ms": 2300},
                    "timing": {"start_ms": 500, "duration_ms": 3900, "easing": "linear"},
                },
                {
                    "stroke_id": "fx-water",
                    "kind": "emitFx",
                    "params": {"fx_id": "water_shimmer", "speed": 0.6, "surface_amp": 0.25},
                    "timing": {"start_ms": 520, "duration_ms": 3900, "easing": "linear"},
                },
                {
                    "stroke_id": "mood-shift",
                    "kind": "setEnvironmentMood",
                    "params": {
                        "mood": {
                            "phase": "day-to-dusk",
                            "window_light": "soft",
                            "desk_material": "wood",
                        }
                    },
                    "timing": {"start_ms": 650, "duration_ms": 4200, "easing": "easeInOutCubic"},
                },
                {
                    "stroke_id": "camera-glide",
                    "kind": "setCameraMove",
                    "params": {"mode": "glide-orbit", "stabilized": True, "speed": 0.24},
                    "timing": {"start_ms": 700, "duration_ms": 3800, "easing": "easeInOutSine"},
                },
            ]
        )
        if mode == "3d":
            strokes.extend(
                [
                    {
                        "stroke_id": "mat-glass",
                        "kind": "applyMaterialFx",
                        "params": {
                            "material_id": "fish_bowl_glass",
                            "shader_id": "glass_refraction_like",
                            "uniforms": {"ior": 1.18, "distortion": 0.12, "rim_strength": 0.45},
                        },
                        "timing": {"start_ms": 200, "duration_ms": 320, "easing": "linear"},
                    },
                    {
                        "stroke_id": "mat-water",
                        "kind": "applyMaterialFx",
                        "params": {
                            "material_id": "water_volume",
                            "shader_id": "water_volume_tint",
                            "uniforms": {"density": 0.36, "blue_shift": 0.42},
                        },
                        "timing": {"start_ms": 220, "duration_ms": 320, "easing": "linear"},
                    },
                    {
                        "stroke_id": "mat-caustic",
                        "kind": "applyMaterialFx",
                        "params": {
                            "material_id": "caustic_overlay",
                            "shader_id": "caustic_overlay_shader",
                            "uniforms": {"intensity": 0.5, "scale": 1.6, "speed": 0.8},
                        },
                        "timing": {"start_ms": 240, "duration_ms": 320, "easing": "linear"},
                    },
                ]
            )

    strokes.append(
        {
            "stroke_id": "insight",
            "kind": "annotateInsight",
            "params": {"text": "Synchronized visual cue active."},
            "timing": {"start_ms": 150, "duration_ms": 150, "easing": "linear"},
        }
    )
    return strokes
