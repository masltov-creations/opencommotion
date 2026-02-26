from __future__ import annotations

import re

COLOR_MAP = {
    "black": "#111827",
    "white": "#f8fafc",
    "red": "#ef4444",
    "orange": "#f97316",
    "yellow": "#facc15",
    "green": "#22c55e",
    "blue": "#3b82f6",
    "purple": "#a855f7",
    "pink": "#ec4899",
    "teal": "#14b8a6",
    "cyan": "#22d3ee",
    "gray": "#9ca3af",
    "grey": "#9ca3af",
    "brown": "#8b5e3c",
}

DRAW_VERBS = ("draw", "sketch", "paint", "render", "illustrate", "show", "create")
SHAPE_ALIASES = {
    "box": "box",
    "square": "square",
    "rectangle": "rectangle",
    "rect": "rectangle",
    "circle": "circle",
    "dot": "dot",
    "line": "line",
    "triangle": "triangle",
}


def _has_word(prompt: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", prompt) is not None


def _extract_color(prompt: str, default: str = "#22d3ee") -> tuple[str, str]:
    for name, hex_color in COLOR_MAP.items():
        if _has_word(prompt, name):
            return name, hex_color
    return "default", default


def _extract_shape(prompt: str) -> str:
    for token, shape in SHAPE_ALIASES.items():
        if _has_word(prompt, token):
            return shape
    return ""


def _draw_intent(prompt: str) -> bool:
    return any(_has_word(prompt, verb) for verb in DRAW_VERBS)


def _size_hint(prompt: str, fallback: int = 96) -> int:
    if "tiny" in prompt or "small" in prompt:
        fallback = 56
    elif "large" in prompt or "big" in prompt:
        fallback = 140

    m = re.search(r"\b(\d{2,3})\s*(?:px|pixel|pixels)\b", prompt)
    if m:
        try:
            fallback = int(m.group(1))
        except ValueError:
            pass
    return max(20, min(260, fallback))


def _shape_dimensions(prompt: str, shape: str) -> tuple[int, int]:
    size = _size_hint(prompt)
    width = size
    height = size
    if shape == "rectangle":
        width = int(size * 1.5)
        height = int(size * 0.85)
    if shape in {"box", "square"}:
        width = size
        height = size
    if "wide" in prompt:
        width = int(width * 1.3)
    if "tall" in prompt:
        height = int(height * 1.3)
    return max(20, width), max(20, height)


def _motion_path(prompt: str, x: int, y: int) -> list[list[int]] | None:
    if "left to right" in prompt:
        return [[x - 140, y], [x + 140, y]]
    if "right to left" in prompt:
        return [[x + 140, y], [x - 140, y]]
    if "up and down" in prompt or "top to bottom" in prompt:
        return [[x, y - 90], [x, y + 90], [x, y - 90]]
    if "orbit" in prompt:
        return [[x + 80, y], [x, y - 80], [x - 80, y], [x, y + 80], [x + 80, y]]
    return None


def _build_shape_strokes(prompt: str, mode: str) -> list[dict]:
    shape = _extract_shape(prompt)
    if not shape:
        return []
    color_name, color_hex = _extract_color(prompt)
    width, height = _shape_dimensions(prompt, shape)
    x, y = 260, 200
    actor_id = f"{shape}_1"

    style: dict = {
        "fill": color_hex,
        "stroke": "#e2e8f0",
        "line_width": max(2, int(width * 0.06)),
        "width": width,
        "height": height,
        "color_name": color_name,
    }

    if shape in {"circle", "dot"}:
        style = {
            "fill": color_hex,
            "stroke": "#e2e8f0",
            "line_width": max(2, int(width * 0.05)),
            "radius": max(8, int(width * (0.5 if shape == "circle" else 0.14))),
            "color_name": color_name,
        }
    elif shape == "line":
        style = {
            "stroke": color_hex,
            "line_width": max(2, int(width * 0.04)),
            "x2": x + 180,
            "y2": y,
            "color_name": color_name,
        }
    elif shape == "triangle":
        style = {
            "fill": color_hex,
            "stroke": "#e2e8f0",
            "line_width": max(2, int(width * 0.05)),
            "size": width,
            "color_name": color_name,
        }

    strokes: list[dict] = [
        {
            "stroke_id": "render-mode-shape",
            "kind": "setRenderMode",
            "params": {"mode": mode},
            "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
        },
        {
            "stroke_id": f"shape-{shape}",
            "kind": "spawnSceneActor",
            "params": {
                "actor_id": actor_id,
                "actor_type": shape,
                "x": x,
                "y": y,
                "style": style,
            },
            "timing": {"start_ms": 60, "duration_ms": 220, "easing": "easeOutCubic"},
        },
        {
            "stroke_id": "shape-note",
            "kind": "annotateInsight",
            "params": {"text": f"Drawing a {color_name if color_name != 'default' else ''} {shape}.".strip()},
            "timing": {"start_ms": 120, "duration_ms": 160, "easing": "linear"},
        },
    ]

    motion = _motion_path(prompt, x, y)
    if motion:
        strokes.append(
            {
                "stroke_id": f"shape-motion-{shape}",
                "kind": "setActorMotion",
                "params": {
                    "actor_id": actor_id,
                    "motion": {
                        "name": "path-motion",
                        "loop": True,
                        "duration_ms": 3200,
                        "path_points": motion,
                    },
                },
                "timing": {"start_ms": 220, "duration_ms": 3200, "easing": "easeInOutSine"},
            }
        )
    return strokes


def _wants_fish_scene(prompt: str) -> bool:
    keys = ("fish bowl", "fishbowl", "goldfish", "fish swimming", "bubbles", "caustic", "aquarium")
    if any(k in prompt for k in keys):
        return True
    return _has_word(prompt, "fish") and (_has_word(prompt, "bowl") or _has_word(prompt, "aquarium"))


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
    if "day-to-night" in prompt or "day to night" in prompt:
        return True
    return _has_word(prompt, "day") and _has_word(prompt, "night")


def _wants_cow_moon_lyric_scene(prompt: str) -> bool:
    has_cow_moon = _has_word(prompt, "cow") and _has_word(prompt, "moon")
    has_lyric_intent = any(key in prompt for key in ("lyric", "lyrics", "bouncing ball", "phrase", "word"))
    return has_cow_moon and has_lyric_intent


def generate_visual_strokes(prompt: str) -> list[dict]:
    p = prompt.lower()
    market_growth_scene = _wants_market_growth_scene(p)
    day_night_scene = _wants_day_night_scene(p)
    cow_moon_lyric_scene = _wants_cow_moon_lyric_scene(p)
    mode = _render_mode(p)
    strokes: list[dict] = []

    if "moonwalk" in p:
        strokes.extend(
            [
                {
                    "stroke_id": "spawn-guide",
                    "kind": "spawnCharacter",
                    "params": {"actor_id": "guide", "x": 180, "y": 190},
                    "timing": {"start_ms": 0, "duration_ms": 200, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "moonwalk-guide",
                    "kind": "animateMoonwalk",
                    "params": {"actor_id": "guide"},
                    "timing": {"start_ms": 250, "duration_ms": 1300, "easing": "easeInOutCubic"},
                },
            ]
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
        bowl_shape = "square" if any(term in p for term in ("square", "box", "cube", "rectangular")) else "round"
        color_name, fish_color = _extract_color(p, default="#f59e0b")
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
                        "style": {"glass": "clear", "desk_anchor": True, "shape": bowl_shape},
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
                        "style": {"species": "goldfish", "palette": color_name, "fill": fish_color},
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

    if not strokes:
        shape_strokes = _build_shape_strokes(p, mode)
        if shape_strokes:
            strokes.extend(shape_strokes)

    if not strokes and _draw_intent(p):
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode-default-draw",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
                },
                {
                    "stroke_id": "fallback-dot",
                    "kind": "spawnSceneActor",
                    "params": {
                        "actor_id": "dot_1",
                        "actor_type": "dot",
                        "x": 250,
                        "y": 190,
                        "style": {"fill": "#22d3ee", "radius": 8},
                    },
                    "timing": {"start_ms": 50, "duration_ms": 180, "easing": "easeOutCubic"},
                },
            ]
        )

    if strokes:
        strokes.append(
            {
                "stroke_id": "insight",
                "kind": "annotateInsight",
                "params": {"text": "Synchronized visual cue active."},
                "timing": {"start_ms": 150, "duration_ms": 150, "easing": "linear"},
            }
        )
    return strokes
