from __future__ import annotations

import hashlib
import os
import random
import re
from typing import Any

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
    "ball": "circle",
    "balls": "circle",
    "dot": "dot",
    "line": "line",
    "triangle": "triangle",
}
NOUN_STOP_WORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "draw",
    "sketch",
    "paint",
    "render",
    "illustrate",
    "show",
    "create",
    "make",
    "build",
    "generate",
    "please",
    "can",
    "could",
    "would",
    "will",
    "just",
    "only",
    "now",
    "then",
    "also",
    "with",
    "and",
    "in",
    "on",
    "to",
    "for",
    "of",
    "is",
    "are",
    "was",
    "were",
    "be",
    "being",
    "been",
    "am",
    "do",
    "does",
    "did",
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "whom",
    "which",
    "explain",
    "describe",
    "tell",
    "about",
    "me",
    "my",
    "your",
    "our",
    "their",
}
COUNT_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "both": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}
VISUAL_TRUE_VALUES = {"1", "true", "yes", "on"}
VISUAL_FALSE_VALUES = {"0", "false", "no", "off"}
LEGACY_TEMPLATE_SCENES_ENV = "OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES"


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
    if re.search(r"\bfish\s*[-_ ]?\s*bowl\b", prompt):
        return True
    if "fishbowl" in prompt:
        return True
    keys = ("goldfish", "fish swimming", "bubbles", "caustic", "aquarium")
    if any(k in prompt for k in keys):
        return True
    return _has_word(prompt, "fish") and (_has_word(prompt, "bowl") or _has_word(prompt, "aquarium"))


def _wants_fish_actor_scene(prompt: str) -> bool:
    if not _has_word(prompt, "fish"):
        return False
    if _wants_fish_scene(prompt):
        return False
    if any(k in prompt for k in ("chart", "graph", "market growth", "segmented attach")):
        return False
    return _draw_intent(prompt) or "swim" in prompt or "swimming" in prompt


def _context_field(context: Any, name: str) -> str | None:
    if context is None:
        return None
    if isinstance(context, dict):
        value = context.get(name)
    else:
        value = getattr(context, name, None)
    if isinstance(value, str):
        value = value.strip()
    return value


def _context_entity_ids(context: Any) -> list[str]:
    if isinstance(context, dict):
        raw = context.get("entity_details")
    else:
        raw = getattr(context, "entity_details", None)
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        candidate = entry.get("id")
        if isinstance(candidate, str) and candidate.strip():
            result.append(candidate.strip())
    return result


def _looks_3d_request(prompt: str) -> bool:
    if re.search(r"\b3\s*[- ]?d\b", prompt):
        return True
    if "three-dimensional" in prompt or "three dimensional" in prompt:
        return True
    return any(token in prompt for token in ("refraction", "volumetric"))


def _render_mode(prompt: str) -> str:
    if _looks_3d_request(prompt):
        return "3d"
    if "2d" in prompt or "stylized layers" in prompt or "parallax" in prompt:
        return "2d"
    return "2d"


def _render_mode_from_context(prompt: str, context: Any) -> str:
    capability = _context_field(context, "capability_brief")
    if isinstance(capability, str):
        match = re.search(r"renderer=([^;\s]+)", capability)
        if match:
            renderer = match.group(1).lower()
            if "3d" in renderer or "three" in renderer:
                return "3d"
            if "2d" in renderer or "svg" in renderer:
                return "2d"
    return _render_mode(prompt)


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


def _legacy_template_scenes_enabled() -> bool:
    raw = os.getenv(LEGACY_TEMPLATE_SCENES_ENV)
    if raw is None or not raw.strip():
        return True
    value = raw.strip().lower()
    if value in VISUAL_FALSE_VALUES:
        return False
    return value in VISUAL_TRUE_VALUES


def _extract_count_for_noun(prompt: str, singular: str, plural: str, *, default: int = 1, max_count: int = 8) -> int:
    noun_pattern = rf"(?:{re.escape(singular)}|{re.escape(plural)})"
    match = re.search(rf"\b(\d{{1,2}})\s+(?:\w+\s+){{0,2}}{noun_pattern}\b", prompt)
    if match:
        try:
            return max(1, min(max_count, int(match.group(1))))
        except ValueError:
            pass

    for token, value in COUNT_WORDS.items():
        if re.search(rf"\b{re.escape(token)}\s+(?:\w+\s+){{0,2}}{noun_pattern}\b", prompt):
            return value

    if _has_word(prompt, plural):
        return min(2, max_count)
    return default


def _extract_ball_count(prompt: str) -> int:
    return _extract_count_for_noun(prompt, singular="ball", plural="balls", default=1, max_count=8)


def _spawn_actor_stroke(
    *,
    stroke_id: str,
    actor_id: str,
    actor_type: str,
    x: int,
    y: int,
    style: dict,
    start_ms: int,
    duration_ms: int = 220,
    easing: str = "easeOutCubic",
) -> dict:
    return {
        "stroke_id": stroke_id,
        "kind": "spawnSceneActor",
        "params": {
            "actor_id": actor_id,
            "actor_type": actor_type,
            "x": x,
            "y": y,
            "style": style,
        },
        "timing": {"start_ms": start_ms, "duration_ms": duration_ms, "easing": easing},
    }


def _set_actor_motion_stroke(
    *,
    stroke_id: str,
    actor_id: str,
    motion_name: str,
    path_points: list[list[int]],
    duration_ms: int,
    start_ms: int,
    easing: str = "easeInOutSine",
    loop: bool = True,
) -> dict:
    return {
        "stroke_id": stroke_id,
        "kind": "setActorMotion",
        "params": {
            "actor_id": actor_id,
            "motion": {
                "name": motion_name,
                "loop": loop,
                "duration_ms": duration_ms,
                "path_points": path_points,
            },
        },
        "timing": {"start_ms": start_ms, "duration_ms": duration_ms, "easing": easing},
    }


def _wants_bouncing_balls_scene(prompt: str) -> bool:
    has_ball = _has_word(prompt, "ball") or _has_word(prompt, "balls")
    has_bounce = any(_has_word(prompt, token) for token in ("bounce", "bouncing", "bouncy"))
    lyric_karaoke_context = any(token in prompt for token in ("lyric", "lyrics", "phrase", "word", "synced to each word"))
    return has_ball and has_bounce and not lyric_karaoke_context


def _build_bouncing_balls_strokes(prompt: str, mode: str) -> list[dict]:
    count = _extract_ball_count(prompt)
    color_name, color_hex = _extract_color(prompt, default="#f43f5e")
    radius = max(12, min(56, int(_size_hint(prompt, fallback=86) * 0.42)))
    gap = max(80, min(170, int(560 / max(count, 1))))
    center_x = 360
    base_y = 258

    palette = [color_hex, "#22d3ee", "#34d399", "#f59e0b", "#60a5fa", "#f472b6", "#a78bfa", "#f87171"]
    strokes: list[dict] = [
        {
            "stroke_id": "render-mode-bouncing-balls",
            "kind": "setRenderMode",
            "params": {"mode": mode},
            "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
        }
    ]

    for idx in range(count):
        actor_id = f"ball_{idx + 1}"
        x = int(round(center_x + (idx - (count - 1) / 2.0) * gap))
        y = base_y
        amp = max(36, min(120, 92 - idx * 8))
        duration_ms = 1100 + idx * 140
        ball_color = palette[idx % len(palette)]
        strokes.extend(
            [
                _spawn_actor_stroke(
                    stroke_id=f"spawn-{actor_id}",
                    actor_id=actor_id,
                    actor_type="circle",
                    x=x,
                    y=y,
                    style={
                        "radius": radius,
                        "fill": ball_color,
                        "stroke": "#e2e8f0",
                        "line_width": 2,
                        "color_name": color_name,
                    },
                    start_ms=80 + idx * 35,
                ),
                _set_actor_motion_stroke(
                    stroke_id=f"bounce-{actor_id}",
                    actor_id=actor_id,
                    motion_name="bounce",
                    duration_ms=duration_ms,
                    path_points=[
                        [x, y],
                        [x, y - amp],
                        [x, y],
                        [x, y - int(amp * 0.82)],
                        [x, y],
                    ],
                    start_ms=180 + idx * 90,
                ),
            ]
        )

    strokes.append(
        {
            "stroke_id": "bouncing-balls-note",
            "kind": "annotateInsight",
            "params": {"text": f"Rendering {count} bouncing ball{'s' if count != 1 else ''} from prompt intent."},
            "timing": {"start_ms": 140, "duration_ms": 220, "easing": "linear"},
        }
    )
    return strokes


def _extract_subject_noun(prompt: str) -> str:
    tokens = re.findall(r"[a-z]+", prompt)
    for token in tokens:
        if token not in NOUN_STOP_WORDS:
            return token
    return "shape"


def _extract_xyz_points(prompt: str) -> tuple[list[list[float]], bool]:
    matches = re.findall(
        r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)(?:\s*,\s*(-?\d+(?:\.\d+)?))?",
        prompt,
    )
    points: list[list[float]] = []
    for x_raw, y_raw, z_raw in matches:
        try:
            x = float(x_raw)
            y = float(y_raw)
            z = float(z_raw) if z_raw else 0.0
        except ValueError:
            continue
        points.append([round(x, 4), round(y, 4), round(z, 4)])
    if len(points) < 2:
        return [], False
    relative = all(0.0 <= row[0] <= 1.0 and 0.0 <= row[1] <= 1.0 for row in points)
    return points, relative


def _seeded_polyline(prompt: str) -> list[list[float]]:
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    points: list[list[float]] = []
    x = 0.14 + rng.random() * 0.12
    for _ in range(6):
        y = 0.24 + rng.random() * 0.52
        points.append([round(x, 4), round(y, 4), 0.0])
        x += 0.11 + rng.random() * 0.1
        x = min(0.9, x)
    return points


def _palette_fish_commands(color_hex: str) -> list[dict]:
    return [
        {
            "op": "polygon",
            "id": "fish_body_script",
            "relative": True,
            "points": [
                [0.36, 0.54, 0.1],
                [0.48, 0.46, 0.12],
                [0.61, 0.52, 0.11],
                [0.49, 0.6, 0.1],
            ],
            "fill": color_hex,
            "stroke": "#e2e8f0",
            "line_width": 2,
        },
        {
            "op": "polygon",
            "id": "fish_tail_script",
            "relative": True,
            "points": [
                [0.35, 0.54, 0.1],
                [0.27, 0.48, 0.08],
                [0.27, 0.6, 0.08],
            ],
            "fill": color_hex,
            "stroke": "#e2e8f0",
            "line_width": 2,
        },
        {
            "op": "dot",
            "id": "fish_eye_script",
            "relative": True,
            "point": [0.55, 0.52, 0.13],
            "radius": 3,
            "color": "#111827",
            "stroke": "#111827",
            "line_width": 1,
        },
        {
            "op": "move",
            "target_id": "fish_body_script",
            "relative": True,
            "duration_ms": 3200,
            "loop": True,
            "path_points": [[0.31, 0.55, 0.12], [0.48, 0.44, 0.14], [0.64, 0.55, 0.12], [0.44, 0.63, 0.1], [0.31, 0.55, 0.12]],
        },
        {
            "op": "move",
            "target_id": "fish_tail_script",
            "relative": True,
            "duration_ms": 3200,
            "loop": True,
            "path_points": [[0.3, 0.55, 0.08], [0.47, 0.44, 0.1], [0.63, 0.55, 0.08], [0.43, 0.63, 0.06], [0.3, 0.55, 0.08]],
        },
    ]


def _build_palette_script_strokes(prompt: str, mode: str) -> list[dict]:
    color_name, color_hex = _extract_color(prompt)
    subject = _extract_subject_noun(prompt)
    points, relative = _extract_xyz_points(prompt)
    line_width = max(2, int(_size_hint(prompt, fallback=96) * 0.045))
    commands: list[dict] = []

    if points:
        commands.append(
            {
                "op": "polyline",
                "id": f"{subject}_polyline",
                "relative": relative,
                "points": points,
                "color": color_hex,
                "line_width": line_width,
            }
        )
        if len(points) >= 3 and any(word in prompt for word in ("fill", "closed", "polygon")):
            commands.append(
                {
                    "op": "polygon",
                    "id": f"{subject}_polygon",
                    "relative": relative,
                    "points": points,
                    "fill": color_hex,
                    "stroke": "#e2e8f0",
                    "line_width": max(1, line_width - 1),
                }
            )
        if any(word in prompt for word in ("move", "animate", "motion", "swim", "orbit", "bounce")):
            commands.append(
                {
                    "op": "move",
                    "target_id": f"{subject}_polyline",
                    "relative": relative,
                    "duration_ms": 3200,
                    "loop": True,
                    "path_points": points,
                }
            )
    elif subject == "fish":
        commands.extend(_palette_fish_commands(color_hex=color_hex))
    else:
        fallback_points = _seeded_polyline(prompt)
        commands.extend(
            [
                {
                    "op": "polyline",
                    "id": f"{subject}_sketch",
                    "relative": True,
                    "points": fallback_points,
                    "color": color_hex,
                    "line_width": line_width,
                },
                {
                    "op": "dot",
                    "id": f"{subject}_anchor",
                    "relative": True,
                    "point": fallback_points[0],
                    "radius": max(3, int(line_width * 0.9)),
                    "color": color_hex,
                    "stroke": "#e2e8f0",
                    "line_width": 1,
                },
            ]
        )
        if any(word in prompt for word in ("move", "animate", "motion", "orbit", "bounce")):
            commands.append(
                {
                    "op": "move",
                    "target_id": f"{subject}_sketch",
                    "relative": True,
                    "duration_ms": 3200,
                    "loop": True,
                    "path_points": fallback_points,
                }
            )

    if not commands:
        return []

    subject_label = subject if subject != "shape" else "scene"
    return [
        {
            "stroke_id": "render-mode-palette-script",
            "kind": "setRenderMode",
            "params": {"mode": mode},
            "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
        },
        {
            "stroke_id": f"palette-script-{subject_label}",
            "kind": "runScreenScript",
            "params": {"program": {"commands": commands}},
            "timing": {"start_ms": 40, "duration_ms": 3600, "easing": "linear"},
        },
        {
            "stroke_id": "palette-script-note",
            "kind": "annotateInsight",
            "params": {
                "text": f"Interface primitives route: no prefab for '{subject_label}', using palette script with point/motion commands."
            },
            "timing": {"start_ms": 120, "duration_ms": 200, "easing": "linear"},
        },
        {
            "stroke_id": "palette-script-tool-note",
            "kind": "annotateInsight",
            "params": {
                "text": f"Palette color: {color_name if color_name != 'default' else color_hex}.",
            },
            "timing": {"start_ms": 150, "duration_ms": 180, "easing": "linear"},
        },
    ]


def generate_visual_strokes(prompt: str, context: Any | None = None) -> list[dict]:
    p = prompt.lower()
    market_growth_scene = _wants_market_growth_scene(p)
    day_night_scene = _wants_day_night_scene(p)
    cow_moon_lyric_scene = _wants_cow_moon_lyric_scene(p)
    bouncing_balls_scene = _wants_bouncing_balls_scene(p)
    fish_scene = _wants_fish_scene(p)
    fish_actor_scene = _wants_fish_actor_scene(p)
    legacy_template_scenes = _legacy_template_scenes_enabled()
    mode = _render_mode_from_context(p, context)
    follow_up = _context_field(context, "turn_phase") == "follow-up"
    existing_entity_ids = _context_entity_ids(context)
    strokes: list[dict] = []

    if legacy_template_scenes and "moonwalk" in p:
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

    if legacy_template_scenes and ("globe" in p or "ufo" in p):
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

    if legacy_template_scenes and ("chart" in p or "adoption" in p or "pie" in p or market_growth_scene):
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

    if legacy_template_scenes and market_growth_scene:
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

    if legacy_template_scenes and day_night_scene:
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

    if legacy_template_scenes and cow_moon_lyric_scene:
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

    if bouncing_balls_scene:
        strokes.extend(_build_bouncing_balls_strokes(prompt=p, mode=mode))

    if fish_scene:
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

    if fish_actor_scene:
        color_name, fish_color = _extract_color(p, default="#f59e0b")
        strokes.extend(
            [
                {
                    "stroke_id": "render-mode-fish",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 100, "easing": "linear"},
                },
                {
                    "stroke_id": "spawn-fish-only",
                    "kind": "spawnSceneActor",
                    "params": {
                        "actor_id": "fish_1",
                        "actor_type": "fish",
                        "x": 300,
                        "y": 205,
                        "style": {"species": "fish", "palette": color_name, "fill": fish_color},
                    },
                    "timing": {"start_ms": 80, "duration_ms": 220, "easing": "easeOutCubic"},
                },
                {
                    "stroke_id": "fish-only-swim",
                    "kind": "setActorMotion",
                    "params": {
                        "actor_id": "fish_1",
                        "motion": {
                            "name": "swim-cycle",
                            "loop": True,
                            "path_points": [[230, 210], [300, 178], [372, 206], [304, 236], [230, 210]],
                            "seed": 17,
                        },
                    },
                    "timing": {"start_ms": 220, "duration_ms": 3600, "easing": "easeInOutSine"},
                },
            ]
        )

    if not strokes:
        shape_strokes = _build_shape_strokes(p, mode)
        if shape_strokes:
            strokes.extend(shape_strokes)

    if not strokes and p.strip():
        # Always produce a visual scene for non-empty prompts, even when the user did not use draw verbs.
        strokes.extend(_build_palette_script_strokes(prompt=p, mode=mode))

    if follow_up and existing_entity_ids:
        strokes.append(
            {
                "stroke_id": "context-followup-motion",
                "kind": "setActorMotion",
                "params": {
                    "actor_id": existing_entity_ids[0],
                    "motion": {
                        "name": "context-followup-nudge",
                        "loop": True,
                        "duration_ms": 2000,
                        "path_points": [[0, 0], [10, 4], [-10, -4], [0, 0]],
                    },
                },
                "timing": {"start_ms": 100, "duration_ms": 2000, "easing": "easeInOutSine"},
            }
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
