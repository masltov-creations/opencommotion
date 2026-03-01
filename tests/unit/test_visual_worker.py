from __future__ import annotations

from services.agents.visual.worker import generate_visual_strokes


def test_draw_box_prompt_generates_fallback_if_llm_is_disabled() -> None:
    strokes = generate_visual_strokes("draw a box")
    kinds = {row["kind"] for row in strokes}
    assert "runScreenScript" in kinds
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    assert any(cmd.get("op") == "polyline" for cmd in commands)


def test_draw_unknown_prompt_routes_to_palette_script_tool() -> None:
    strokes = generate_visual_strokes("draw a rocket with motion")
    kinds = [row["kind"] for row in strokes]
    assert "runScreenScript" in kinds
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    assert any(cmd.get("op") in {"polyline", "polygon", "dot"} for cmd in commands)
    assert any(cmd.get("op") == "move" for cmd in commands)


def test_non_draw_prompt_still_routes_to_visual_primitives() -> None:
    strokes = generate_visual_strokes("explain tcp handshake")
    kinds = [row["kind"] for row in strokes]
    assert "runScreenScript" in kinds
    note = next(row for row in strokes if row["kind"] == "annotateInsight")
    assert "Fallback generated seeded" in str(note.get("params", {}).get("text", ""))


def test_draw_prompt_with_relative_xyz_points_uses_script_points() -> None:
    strokes = generate_visual_strokes("draw shape points 0.2,0.3,0.1 0.6,0.3,0.2 0.8,0.7,0.3 and animate")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    polyline = next(cmd for cmd in commands if cmd.get("op") == "polyline")
    assert polyline["relative"] is True
    assert len(polyline["points"]) == 3



def test_llm_visual_path_skipped_when_provider_is_heuristic(monkeypatch) -> None:
    # heuristic provider (the default) must never invoke build_adapters
    # Note: the visual worker reads OPENCOMMOTION_LLM_PROVIDER (not VISUAL_LLM_PROVIDER)
    monkeypatch.delenv("OPENCOMMOTION_LLM_PROVIDER", raising=False)
    import services.agents.text.adapters as _adapters_mod
    calls: list[str] = []
    original_build = _adapters_mod.build_adapters
    def mock_build(*args, **kwargs):  # noqa: ANN001,ANN002,ANN003
        calls.append("called")
        return original_build(*args, **kwargs)
    monkeypatch.setattr(_adapters_mod, "build_adapters", mock_build)
    generate_visual_strokes("draw a futuristic city")
    assert not calls, "build_adapters must not be called when provider=heuristic"
