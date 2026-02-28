from __future__ import annotations

from services.agents.coherence import (
    _parse_coherence_response,
    _summarize_strokes,
    assess_coherence,
)


# ---------------------------------------------------------------------------
# _parse_coherence_response
# ---------------------------------------------------------------------------


def test_valid_coherent_json() -> None:
    raw = '{"ok": true, "reason": "coherent"}'
    result = _parse_coherence_response(raw)
    assert result["ok"] is True
    assert "coherent" in result["reason"]


def test_valid_incoherent_json() -> None:
    raw = '{"ok": false, "reason": "text describes sunset but visual shows a house", "adjustments": ["add sun shape"]}'
    result = _parse_coherence_response(raw)
    assert result["ok"] is False
    assert "sunset" in result["reason"]
    assert len(result["adjustments"]) == 1


def test_markdown_fenced_json() -> None:
    raw = '```json\n{"ok": true, "reason": "all good"}\n```'
    result = _parse_coherence_response(raw)
    assert result["ok"] is True


def test_no_json_returns_ok_skipped() -> None:
    result = _parse_coherence_response("I think the scenes are coherent")
    assert result["ok"] is True
    assert result.get("skipped") is True


def test_bad_json_returns_ok_skipped() -> None:
    result = _parse_coherence_response("{bad json content")
    assert result["ok"] is True
    assert result.get("skipped") is True


def test_reason_truncated_to_120() -> None:
    raw = '{"ok": false, "reason": "' + "x" * 200 + '"}'
    result = _parse_coherence_response(raw)
    assert len(result["reason"]) <= 120


# ---------------------------------------------------------------------------
# _summarize_strokes
# ---------------------------------------------------------------------------


def test_summarize_strokes_extracts_kinds() -> None:
    strokes = [
        {"kind": "setRenderMode", "params": {"mode": "2d"}},
        {"kind": "spawnSceneActor", "params": {"actor_type": "circle"}},
        {"kind": "annotateInsight", "params": {"text": "test"}},
    ]
    summary = _summarize_strokes(strokes)
    assert "setRenderMode" in summary
    assert "circle" in summary


def test_summarize_strokes_extracts_script_commands() -> None:
    strokes = [
        {
            "kind": "runScreenScript",
            "params": {
                "program": {
                    "commands": [
                        {"op": "rect", "id": "wall"},
                        {"op": "polygon", "id": "roof"},
                    ]
                }
            },
        },
    ]
    summary = _summarize_strokes(strokes)
    assert "rect:wall" in summary
    assert "polygon:roof" in summary


def test_summarize_empty_strokes() -> None:
    summary = _summarize_strokes([])
    assert "Stroke kinds:" in summary


# ---------------------------------------------------------------------------
# assess_coherence (heuristic mode)
# ---------------------------------------------------------------------------


def test_assess_coherence_heuristic_mode_skips(monkeypatch) -> None:
    monkeypatch.delenv("OPENCOMMOTION_LLM_PROVIDER", raising=False)
    result = assess_coherence(
        prompt="draw a house",
        text="Here is a cozy house.",
        visual_strokes=[{"kind": "setRenderMode", "params": {"mode": "2d"}}],
    )
    assert result["ok"] is True
    assert result.get("skipped") is True
    assert "heuristic" in result.get("reason", "")
