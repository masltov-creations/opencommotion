from __future__ import annotations

import json

import pytest

from services.agents.visual.worker import (
    _SUPPORTED_OPS,
    _fallback_visual_strokes,
    _parse_llm_visual_response,
    _translate_unsupported_op,
)


# ---------------------------------------------------------------------------
# _translate_unsupported_op
# ---------------------------------------------------------------------------


def test_supported_op_passes_through() -> None:
    cmd = {"op": "rect", "id": "r1", "point": [10, 20], "width": 50, "height": 30, "fill": "#ff0000"}
    result, warning = _translate_unsupported_op(cmd)
    assert result is cmd  # exact same object, no copy
    assert warning is None


def test_known_unsupported_op_maps_to_closest() -> None:
    cmd = {"op": "star", "id": "s1", "color": "#facc15"}
    result, warning = _translate_unsupported_op(cmd)
    assert result["op"] == "polygon"
    assert result["id"] == "s1"
    assert warning is not None
    assert "'star'" in warning and "'polygon'" in warning


def test_arrow_maps_to_polyline() -> None:
    cmd = {"op": "arrow", "id": "a1", "color": "#ef4444"}
    result, _ = _translate_unsupported_op(cmd)
    assert result["op"] == "polyline"
    assert "points" in result  # default points injected
    assert result["color"] == "#ef4444"


def test_label_maps_to_text() -> None:
    cmd = {"op": "label", "id": "l1"}
    result, _ = _translate_unsupported_op(cmd)
    assert result["op"] == "text"
    assert result["text"] == "label"
    assert "point" in result
    assert "fill" in result


def test_completely_unknown_op_defaults_to_rect() -> None:
    cmd = {"op": "sparkle_burst", "id": "x1", "color": "#bada55"}
    result, warning = _translate_unsupported_op(cmd)
    assert result["op"] == "rect"
    assert result["id"] == "x1"
    assert warning is not None
    assert "'sparkle_burst'" in warning


def test_id_injected_when_missing() -> None:
    cmd = {"op": "gradient"}
    result, _ = _translate_unsupported_op(cmd)
    assert result["op"] == "rect"
    assert result["id"] == "translated_gradient"


def test_all_supported_ops_pass_through() -> None:
    for op in _SUPPORTED_OPS:
        cmd = {"op": op, "id": f"test_{op}"}
        result, warning = _translate_unsupported_op(cmd)
        assert result["op"] == op
        assert warning is None


# ---------------------------------------------------------------------------
# _parse_llm_visual_response
# ---------------------------------------------------------------------------


def test_valid_json_with_supported_ops() -> None:
    raw = json.dumps({"commands": [
        {"op": "rect", "id": "r1", "point": [10, 20], "width": 50, "height": 30, "fill": "#ff0000"},
        {"op": "circle", "id": "c1", "point": [100, 100], "radius": 40, "fill": "#00ff00"},
    ]})
    commands, warnings = _parse_llm_visual_response(raw)
    assert len(commands) == 2
    assert not warnings


def test_unsupported_ops_are_translated_not_dropped() -> None:
    raw = json.dumps({"commands": [
        {"op": "rect", "id": "r1", "point": [10, 20], "width": 50, "height": 30, "fill": "#ff0000"},
        {"op": "star", "id": "s1", "color": "#facc15"},
        {"op": "arc", "id": "a1"},
    ]})
    commands, warnings = _parse_llm_visual_response(raw)
    assert len(commands) == 3  # all preserved, none dropped
    ops = [cmd["op"] for cmd in commands]
    assert ops == ["rect", "polygon", "polyline"]
    assert len(warnings) == 2
    assert any("star" in w for w in warnings)
    assert any("arc" in w for w in warnings)


def test_markdown_fenced_json_still_parses() -> None:
    raw = '```json\n{"commands": [{"op": "dot", "id": "d1", "point": [10, 20], "radius": 5, "color": "#ff0000"}]}\n```'
    commands, warnings = _parse_llm_visual_response(raw)
    assert len(commands) == 1
    assert commands[0]["op"] == "dot"
    assert not warnings


def test_no_json_returns_empty_with_warning() -> None:
    commands, warnings = _parse_llm_visual_response("Here is my scene description in natural language.")
    assert commands == []
    assert len(warnings) == 1
    assert "no JSON object" in warnings[0]


def test_bad_json_returns_empty_with_warning() -> None:
    # Balanced braces but invalid JSON (trailing comma) triggers json.JSONDecodeError
    commands, warnings = _parse_llm_visual_response('{"commands": [{"op": "rect",}]}')
    assert commands == []
    assert len(warnings) == 1
    assert "JSON" in warnings[0]


def test_missing_commands_key_returns_warning() -> None:
    raw = json.dumps({"shapes": [{"op": "rect"}]})
    commands, warnings = _parse_llm_visual_response(raw)
    assert commands == []
    assert any("commands" in w for w in warnings)


# ---------------------------------------------------------------------------
# _fallback_visual_strokes
# ---------------------------------------------------------------------------


def test_fallback_returns_non_empty_strokes() -> None:
    strokes = _fallback_visual_strokes("futuristic city", "2d", ["adapter error"])
    assert len(strokes) > 0
    kinds = {s["kind"] for s in strokes}
    assert "runScreenScript" in kinds
    assert "annotateInsight" in kinds


def test_fallback_includes_warning_text() -> None:
    strokes = _fallback_visual_strokes("test", "2d", ["could not connect"])
    warning_stroke = next(s for s in strokes if s["kind"] == "annotateInsight")
    assert "could not connect" in warning_stroke["params"]["text"]


def test_fallback_includes_prompt_label() -> None:
    strokes = _fallback_visual_strokes("a beautiful sunset", "2d", [])
    script = next(s for s in strokes if s["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    label = next(c for c in commands if c.get("id") == "fallback_label")
    assert "sunset" in label["text"]
