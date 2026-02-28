from __future__ import annotations

import hashlib
import json
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


# ---------------------------------------------------------------------------
# LLM-powered freeform visual generation
# ---------------------------------------------------------------------------

VISUAL_LLM_PROVIDER_ENV = "OPENCOMMOTION_LLM_PROVIDER"
VISUAL_LLM_TIMEOUT_ENV = "OPENCOMMOTION_LLM_TIMEOUT_S"
_VALID_LLM_PROVIDERS_FOR_VISUAL = {"ollama", "openai-compatible", "codex-cli", "openclaw-cli", "openclaw-openai"}


def _llm_provider_for_visual() -> str:
    return os.getenv(VISUAL_LLM_PROVIDER_ENV, "heuristic").strip().lower()


def _llm_timeout_for_visual() -> float:
    raw = os.getenv(VISUAL_LLM_TIMEOUT_ENV, "20").strip()
    try:
        return min(max(float(raw), 0.5), 60.0)
    except ValueError:
        return 20.0


def _visual_dsl_system_prompt() -> str:
    return (
        "You are OpenCommotion visual scene compiler. Generate a rendering script.\n"
        "\n"
        "CANVAS: 720x360 pixels. Origin top-left. x: 0-720, y: 0-360.\n"
        "\n"
        "COMMANDS (each is a JSON object in the commands array):\n"
        '- dot:      {"op":"dot",      "id":"<str>", "point":[x,y],         "radius":<int>, "color":"#hex"}\n'
        '- circle:   {"op":"circle",   "id":"<str>", "point":[cx,cy],       "radius":<int>, "fill":"#hex", "stroke":"#hex", "line_width":<int>}\n'
        '- ellipse:  {"op":"ellipse",  "id":"<str>", "point":[cx,cy],       "rx":<int>, "ry":<int>, "fill":"#hex", "stroke":"#hex", "line_width":<int>}\n'
        '- rect:     {"op":"rect",     "id":"<str>", "point":[x,y],         "width":<int>, "height":<int>, "fill":"#hex", "stroke":"#hex", "line_width":<int>}\n'
        '- line:     {"op":"line",     "id":"<str>", "points":[[x1,y1],[x2,y2]], "color":"#hex", "line_width":<int>}\n'
        '- polyline: {"op":"polyline", "id":"<str>", "points":[[x1,y1],...], "color":"#hex", "line_width":<int>}\n'
        '- polygon:  {"op":"polygon",  "id":"<str>", "points":[[x1,y1],...], "fill":"#hex", "stroke":"#hex", "line_width":<int>}\n'
        '- text:     {"op":"text",     "id":"<str>", "point":[x,y],         "text":"<string>", "fill":"#hex", "font_size":<int>}\n'
        '- move:     {"op":"move",     "target_id":"<existing_id>",          "path_points":[[x1,y1],...], "duration_ms":<int>, "loop":<bool>}\n'
        '- annotate: {"op":"annotate", "text":"<description>"}\n'
        "\n"
        "RULES:\n"
        "1. Every shape command (dot/circle/ellipse/rect/line/polyline/polygon/text) needs a unique id string.\n"
        "2. move uses target_id referencing an existing shape — do NOT add an id field to move.\n"
        "3. Absolute pixel coordinates within 720x360.\n"
        "4. Colors are #rrggbb hex codes. Named aliases: red=#ef4444, blue=#3b82f6, green=#22c55e, yellow=#facc15, orange=#f97316, purple=#a855f7, teal=#14b8a6, pink=#ec4899, white=#f8fafc, black=#111827, gray=#9ca3af.\n"
        "5. Compose 4-14 primitives that meaningfully represent the scene described.\n"
        "6. Include a move command for any object that should animate or move.\n"
        "7. Return ONLY the JSON. No markdown fences, no prose, no explanation.\n"
        "\n"
        'Return exactly: {"commands": [...]}'  # noqa: S105
    )


def _parse_llm_visual_response(raw: str) -> list[dict]:
    """Extract a list of runScreenScript command dicts from an LLM response."""
    clean = raw.strip()
    # Strip markdown code fences
    if clean.startswith("```"):
        lines = clean.splitlines()
        inner = [ln for ln in lines[1:] if not ln.startswith("```")]
        clean = "\n".join(inner).strip()
    # Find the JSON object
    brace_start = clean.find("{")
    if brace_start == -1:
        return []
    clean = clean[brace_start:]
    depth = 0
    end = 0
    for i, ch in enumerate(clean):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == 0:
        return []
    try:
        payload = json.loads(clean[:end])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    commands = payload.get("commands")
    if not isinstance(commands, list):
        return []
    return [cmd for cmd in commands if isinstance(cmd, dict) and isinstance(cmd.get("op"), str)]


def _build_llm_visual_script(prompt: str, mode: str) -> list[dict]:
    """Use the configured LLM to generate a freeform visual scene via the DSL."""
    provider = _llm_provider_for_visual()
    if provider not in _VALID_LLM_PROVIDERS_FOR_VISUAL:
        return []
    try:
        from services.agents.text.adapters import AdapterError, build_adapters  # noqa: PLC0415
        adapters_map = build_adapters(timeout_s=_llm_timeout_for_visual())
        adapter = adapters_map.get(provider)
        if adapter is None:
            return []
        system_prompt = _visual_dsl_system_prompt()
        user_request = f"Scene to render: {prompt}\nRender mode: {mode}"
        raw = (adapter.generate(user_request, system_prompt_override=system_prompt) or "").strip()
        if not raw:
            return []
        commands = _parse_llm_visual_response(raw)
        if not commands:
            return []
        return [
            {
                "stroke_id": "render-mode-llm-visual",
                "kind": "setRenderMode",
                "params": {"mode": mode},
                "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
            },
            {
                "stroke_id": "llm-visual-script",
                "kind": "runScreenScript",
                "params": {"program": {"commands": commands}},
                "timing": {"start_ms": 40, "duration_ms": 4800, "easing": "linear"},
            },
            {
                "stroke_id": "llm-visual-note",
                "kind": "annotateInsight",
                "params": {"text": f"LLM visual ({provider}): {prompt[:72].strip()}"},
                "timing": {"start_ms": 120, "duration_ms": 160, "easing": "linear"},
            },
        ]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Entity-decomposition: compose known real-world objects from DSL primitives
# ---------------------------------------------------------------------------

_ENTITY_NOUN_MAP: dict[str, str] = {
    "rocket": "rocket", "spaceship": "rocket", "spacecraft": "rocket",
    "house": "house", "home": "house", "building": "building", "tower": "building",
    "tree": "tree", "forest": "tree",
    "sun": "sun", "daytime": "sun",
    "star": "star", "stars": "star",
    "cloud": "cloud", "clouds": "cloud",
    "mountain": "mountain", "mountains": "mountain", "hill": "mountain",
    "car": "car", "vehicle": "car",
    "flower": "flower", "flowers": "flower",
    "person": "person", "man": "person", "woman": "person", "human": "person",
    "bird": "bird", "birds": "bird",
    "heart": "heart",
    "wave": "wave", "ocean": "wave", "sea": "wave", "water": "wave",
    "boat": "boat", "ship": "boat",
    "sunset": "sunset", "sunrise": "sunset",
    "moon": "moon",
    "planet": "planet", "earth": "planet",
    "butterfly": "butterfly",
    "snowflake": "snowflake",
}


def _entity_shape_commands(entity: str, color_hex: str, has_motion: bool) -> list[dict]:
    """Return runScreenScript commands for a known entity."""
    c = color_hex

    if entity == "rocket":
        cmds: list[dict] = [
            {"op": "polygon", "id": "rocket_nose", "points": [[350, 105], [370, 105], [360, 62]], "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "rect", "id": "rocket_body", "point": [344, 105], "width": 32, "height": 84, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "rocket_fin_l", "points": [[344, 155], [318, 196], [344, 184]], "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "rocket_fin_r", "points": [[376, 155], [402, 196], [376, 184]], "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "ellipse", "id": "rocket_flame", "point": [360, 202], "rx": 11, "ry": 18, "fill": "#f97316"},
            {"op": "dot", "id": "rocket_window", "point": [360, 132], "radius": 9, "color": "#bae6fd"},
        ]
        if has_motion:
            cmds.append({"op": "move", "target_id": "rocket_body", "path_points": [[360, 150], [360, 100], [380, 60], [360, 24]], "duration_ms": 3600, "loop": True})
        return cmds

    if entity == "house":
        return [
            {"op": "rect", "id": "house_walls", "point": [270, 168], "width": 180, "height": 130, "fill": "#f59e0b", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "house_roof", "points": [[258, 168], [360, 82], [462, 168]], "fill": "#ef4444", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "rect", "id": "house_door", "point": [336, 230], "width": 48, "height": 68, "fill": "#78350f", "stroke": "#e2e8f0", "line_width": 1},
            {"op": "rect", "id": "house_win_l", "point": [283, 185], "width": 42, "height": 38, "fill": "#bae6fd", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "rect", "id": "house_win_r", "point": [395, 185], "width": 42, "height": 38, "fill": "#bae6fd", "stroke": "#e2e8f0", "line_width": 2},
        ]

    if entity == "building":
        return [
            {"op": "rect", "id": "bldg_body", "point": [300, 80], "width": 120, "height": 220, "fill": "#475569", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "rect", "id": "bldg_w1", "point": [312, 96], "width": 28, "height": 22, "fill": "#bae6fd"},
            {"op": "rect", "id": "bldg_w2", "point": [380, 96], "width": 28, "height": 22, "fill": "#bae6fd"},
            {"op": "rect", "id": "bldg_w3", "point": [312, 134], "width": 28, "height": 22, "fill": "#bae6fd"},
            {"op": "rect", "id": "bldg_w4", "point": [380, 134], "width": 28, "height": 22, "fill": "#bae6fd"},
            {"op": "rect", "id": "bldg_door", "point": [340, 262], "width": 40, "height": 38, "fill": "#78350f"},
        ]

    if entity == "tree":
        leaf = c if c not in ("#22d3ee", "#f8fafc", "#111827") else "#22c55e"
        return [
            {"op": "rect", "id": "tree_trunk", "point": [348, 226], "width": 24, "height": 90, "fill": "#8b5e3c", "stroke": "#78350f", "line_width": 2},
            {"op": "polygon", "id": "tree_canopy_l", "points": [[270, 232], [360, 110], [450, 232]], "fill": leaf, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "tree_canopy_t", "points": [[294, 182], [360, 82], [426, 182]], "fill": _lighten_color(leaf), "stroke": "#e2e8f0", "line_width": 2},
        ]

    if entity == "sun":
        rays = []
        import math
        for i in range(8):
            angle = i * math.pi / 4
            x1 = round(360 + math.cos(angle) * 52)
            y1 = round(100 + math.sin(angle) * 52)
            x2 = round(360 + math.cos(angle) * 74)
            y2 = round(100 + math.sin(angle) * 74)
            rays.append({"op": "line", "id": f"sun_ray_{i}", "points": [[x1, y1], [x2, y2]], "color": "#fde68a", "line_width": 3})
        return [
            {"op": "circle", "id": "sun_body", "point": [360, 100], "radius": 46, "fill": "#fde68a", "stroke": "#fbbf24", "line_width": 3},
            *rays,
        ]

    if entity == "star":
        import math
        pts: list[list[int]] = []
        for i in range(10):
            r = 46 if i % 2 == 0 else 20
            angle = i * math.pi / 5 - math.pi / 2
            pts.append([round(360 + math.cos(angle) * r), round(140 + math.sin(angle) * r)])
        return [{"op": "polygon", "id": "star_shape", "points": pts, "fill": "#facc15", "stroke": "#fbbf24", "line_width": 2}]

    if entity == "cloud":
        return [
            {"op": "ellipse", "id": "cloud_main", "point": [360, 110], "rx": 72, "ry": 36, "fill": "#e2e8f0"},
            {"op": "ellipse", "id": "cloud_l", "point": [306, 125], "rx": 46, "ry": 28, "fill": "#e2e8f0"},
            {"op": "ellipse", "id": "cloud_r", "point": [414, 122], "rx": 52, "ry": 30, "fill": "#e2e8f0"},
        ]

    if entity == "mountain":
        return [
            {"op": "polygon", "id": "mountain_bg", "points": [[80, 300], [250, 100], [420, 300]], "fill": "#475569", "stroke": "#64748b", "line_width": 2},
            {"op": "polygon", "id": "mountain_fg", "points": [[300, 300], [500, 140], [700, 300]], "fill": "#334155", "stroke": "#64748b", "line_width": 2},
            {"op": "polygon", "id": "mountain_snow", "points": [[465, 162], [500, 140], [535, 162], [510, 176], [490, 176]], "fill": "#f8fafc"},
        ]

    if entity == "car":
        return [
            {"op": "rect", "id": "car_body", "point": [222, 200], "width": 276, "height": 80, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "car_roof", "points": [[284, 200], [330, 155], [440, 155], [488, 200]], "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "circle", "id": "car_wheel_l", "point": [298, 286], "radius": 28, "fill": "#1e293b", "stroke": "#94a3b8", "line_width": 4},
            {"op": "circle", "id": "car_wheel_r", "point": [422, 286], "radius": 28, "fill": "#1e293b", "stroke": "#94a3b8", "line_width": 4},
            {"op": "rect", "id": "car_win", "point": [338, 162], "width": 94, "height": 38, "fill": "#bae6fd", "stroke": "#e2e8f0", "line_width": 1},
        ]

    if entity == "flower":
        import math
        petals = []
        for i in range(6):
            angle = i * math.pi / 3
            px = round(360 + math.cos(angle) * 44)
            py = round(180 + math.sin(angle) * 44)
            petals.append({"op": "circle", "id": f"flower_petal_{i}", "point": [px, py], "radius": 22, "fill": c, "stroke": "#e2e8f0", "line_width": 1})
        return [
            *petals,
            {"op": "circle", "id": "flower_center", "point": [360, 180], "radius": 18, "fill": "#fde68a", "stroke": "#fbbf24", "line_width": 2},
            {"op": "line", "id": "flower_stem", "points": [[360, 202], [360, 298]], "color": "#22c55e", "line_width": 4},
        ]

    if entity == "person":
        return [
            {"op": "circle", "id": "person_head", "point": [360, 120], "radius": 28, "fill": "#fde68a", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "rect", "id": "person_body", "point": [338, 150], "width": 44, "height": 74, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "line", "id": "person_arm_l", "points": [[338, 165], [296, 210]], "color": c, "line_width": 6},
            {"op": "line", "id": "person_arm_r", "points": [[382, 165], [424, 210]], "color": c, "line_width": 6},
            {"op": "line", "id": "person_leg_l", "points": [[350, 224], [332, 296]], "color": "#1e293b", "line_width": 6},
            {"op": "line", "id": "person_leg_r", "points": [[370, 224], [388, 296]], "color": "#1e293b", "line_width": 6},
        ]

    if entity == "bird":
        return [
            {"op": "polyline", "id": "bird_1", "points": [[180, 100], [210, 84], [240, 100]], "color": c, "line_width": 3},
            {"op": "polyline", "id": "bird_2", "points": [[310, 70], [346, 52], [382, 70]], "color": c, "line_width": 3},
            {"op": "polyline", "id": "bird_3", "points": [[450, 90], [484, 74], [518, 90]], "color": c, "line_width": 3},
        ]

    if entity == "heart":
        import math
        pts = []
        for i in range(36):
            t = i * 2 * math.pi / 36
            x = round(360 + 44 * (16 * math.sin(t) ** 3) / 16)
            y = round(170 - 44 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16)
            pts.append([x, y])
        return [{"op": "polygon", "id": "heart", "points": pts, "fill": "#ef4444", "stroke": "#e2e8f0", "line_width": 2}]

    if entity == "wave":
        import math
        pts = [[round(i * 720 / 35), round(240 + math.sin(i * 0.55) * 50)] for i in range(36)]
        return [
            {"op": "polyline", "id": "wave_1", "points": pts, "color": "#38bdf8", "line_width": 4},
            {"op": "polyline", "id": "wave_2", "points": [[p[0], p[1] + 26] for p in pts], "color": "#0ea5e9", "line_width": 3},
        ]

    if entity == "boat":
        cmds = [
            {"op": "polygon", "id": "boat_hull", "points": [[220, 220], [500, 220], [470, 280], [250, 280]], "fill": "#78350f", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "boat_sail_l", "points": [[360, 90], [360, 215], [250, 215]], "fill": "#f8fafc", "stroke": "#e2e8f0", "line_width": 2},
            {"op": "polygon", "id": "boat_sail_r", "points": [[360, 90], [360, 215], [460, 215]], "fill": "#e2e8f0", "stroke": "#cbd5e1", "line_width": 2},
            {"op": "line", "id": "boat_mast", "points": [[360, 215], [360, 80]], "color": "#78350f", "line_width": 4},
        ]
        if has_motion:
            cmds.append({"op": "move", "target_id": "boat_hull", "path_points": [[360, 250], [320, 248], [280, 252], [240, 248], [200, 252]], "duration_ms": 4200, "loop": True})
        return cmds

    if entity == "sunset":
        import math
        rays = []
        for i in range(8):
            angle = i * math.pi / 8
            x1 = round(360 + math.cos(angle) * 56)
            y1 = round(250 + math.sin(angle) * 56)
            x2 = round(360 + math.cos(angle) * 82)
            y2 = round(250 + math.sin(angle) * 82)
            rays.append({"op": "line", "id": f"sunset_ray_{i}", "points": [[x1, y1], [x2, y2]], "color": "#fbbf24", "line_width": 3})
        return [
            *rays,
            {"op": "circle", "id": "sunset_sun", "point": [360, 250], "radius": 50, "fill": "#f97316", "stroke": "#fbbf24", "line_width": 3},
            {"op": "polyline", "id": "sunset_horizon", "points": [[0, 280], [720, 280]], "color": "#0ea5e9", "line_width": 2},
            {"op": "polyline", "id": "sunset_wave_1", "points": [[0, 300], [120, 290], [240, 305], [360, 292], [480, 308], [600, 294], [720, 302]], "color": "#0284c7", "line_width": 3},
        ]

    if entity == "moon":
        return [
            {"op": "circle", "id": "moon_body", "point": [360, 140], "radius": 52, "fill": "#fef3c7", "stroke": "#fde68a", "line_width": 2},
            {"op": "circle", "id": "moon_shadow", "point": [390, 125], "radius": 44, "fill": "#0f172a"},
            {"op": "dot", "id": "moon_crater_1", "point": [340, 150], "radius": 8, "color": "#fde68a"},
            {"op": "dot", "id": "moon_crater_2", "point": [320, 125], "radius": 5, "color": "#fde68a"},
        ]

    if entity == "planet":
        return [
            {"op": "circle", "id": "planet_body", "point": [360, 180], "radius": 60, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "ellipse", "id": "planet_ring", "point": [360, 180], "rx": 92, "ry": 22, "fill": "none", "stroke": "#f59e0b", "line_width": 4},
            {"op": "ellipse", "id": "planet_band", "point": [360, 180], "rx": 60, "ry": 18, "fill": "none", "stroke": "#7c3aed", "line_width": 3},
        ]

    if entity == "butterfly":
        return [
            {"op": "ellipse", "id": "butterfly_wing_lu", "point": [310, 148], "rx": 46, "ry": 36, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "ellipse", "id": "butterfly_wing_ru", "point": [410, 148], "rx": 46, "ry": 36, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "ellipse", "id": "butterfly_wing_ll", "point": [318, 200], "rx": 34, "ry": 24, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "ellipse", "id": "butterfly_wing_rl", "point": [402, 200], "rx": 34, "ry": 24, "fill": c, "stroke": "#e2e8f0", "line_width": 2},
            {"op": "line", "id": "butterfly_body", "points": [[360, 132], [360, 225]], "color": "#111827", "line_width": 4},
            {"op": "polyline", "id": "butterfly_ant_l", "points": [[360, 132], [336, 108], [326, 98]], "color": "#111827", "line_width": 2},
            {"op": "polyline", "id": "butterfly_ant_r", "points": [[360, 132], [384, 108], [394, 98]], "color": "#111827", "line_width": 2},
        ]

    if entity == "snowflake":
        import math
        lines: list[dict] = []
        for i in range(6):
            angle = i * math.pi / 3
            x2 = round(360 + math.cos(angle) * 66)
            y2 = round(180 + math.sin(angle) * 66)
            lines.append({"op": "line", "id": f"sf_arm_{i}", "points": [[360, 180], [x2, y2]], "color": c if c != "#22d3ee" else "#bae6fd", "line_width": 3})
            bx1 = round(360 + math.cos(angle) * 36 + math.cos(angle + math.pi / 3) * 14)
            by1 = round(180 + math.sin(angle) * 36 + math.sin(angle + math.pi / 3) * 14)
            bx2 = round(360 + math.cos(angle) * 36 - math.cos(angle + math.pi / 3) * 14)
            by2 = round(180 + math.sin(angle) * 36 - math.sin(angle + math.pi / 3) * 14)
            lines.append({"op": "line", "id": f"sf_branch_{i}", "points": [[bx1, by1], [bx2, by2]], "color": c if c != "#22d3ee" else "#bae6fd", "line_width": 2})
        return [*lines, {"op": "dot", "id": "sf_center", "point": [360, 180], "radius": 6, "color": c if c != "#22d3ee" else "#bae6fd"}]

    return []


def _lighten_color(hex_color: str) -> str:
    """Very rough hex color lightener for tree layer variation."""
    try:
        r = min(255, int(hex_color[1:3], 16) + 48)
        g = min(255, int(hex_color[3:5], 16) + 48)
        b = min(255, int(hex_color[5:7], 16) + 16)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:  # noqa: BLE001
        return hex_color


def _build_entity_scene_strokes(prompt: str, mode: str) -> list[dict]:
    """Build a meaningful scene from entity shape templates."""
    tokens = re.findall(r"[a-z]+", prompt)
    for token in tokens:
        entity = _ENTITY_NOUN_MAP.get(token, "")
        if entity:
            _, color_hex = _extract_color(prompt, default="#22d3ee")
            has_motion = any(w in prompt for w in ("move", "animate", "motion", "fly", "swim", "orbit", "bounce", "drift", "float"))
            commands = _entity_shape_commands(entity, color_hex, has_motion)
            if not commands:
                return []
            subject_label = token
            return [
                {
                    "stroke_id": "render-mode-entity",
                    "kind": "setRenderMode",
                    "params": {"mode": mode},
                    "timing": {"start_ms": 0, "duration_ms": 80, "easing": "linear"},
                },
                {
                    "stroke_id": f"entity-scene-{subject_label}",
                    "kind": "runScreenScript",
                    "params": {"program": {"commands": commands}},
                    "timing": {"start_ms": 40, "duration_ms": 3600, "easing": "linear"},
                },
                {
                    "stroke_id": "entity-note",
                    "kind": "annotateInsight",
                    "params": {"text": f"Interface primitives route: {subject_label} scene from entity composition."},
                    "timing": {"start_ms": 120, "duration_ms": 160, "easing": "linear"},
                },
            ]
    return []


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
    mode = _render_mode_from_context(p, context)
    follow_up = _context_field(context, "turn_phase") == "follow-up"
    existing_entity_ids = _context_entity_ids(context)
    strokes: list[dict] = []

    if not strokes:
        shape_strokes = _build_shape_strokes(p, mode)
        if shape_strokes:
            strokes.extend(shape_strokes)

    # LLM-powered freeform visual generation: richer than regex heuristics for novel prompts.
    if not strokes:
        llm_strokes = _build_llm_visual_script(p, mode)
        if llm_strokes:
            strokes.extend(llm_strokes)

    # Entity-decomposition: compose known real-world objects from DSL primitives when LLM is not available.
    if not strokes:
        entity_strokes = _build_entity_scene_strokes(p, mode)
        if entity_strokes:
            strokes.extend(entity_strokes)

    if not strokes and p.strip():
        # Final fallback: seeded polyline palette script.
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
