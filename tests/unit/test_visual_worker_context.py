from services.agents.visual.worker import generate_visual_strokes


def test_render_mode_from_context():
    strokes = generate_visual_strokes(
        "draw a lively scene",
        context={"capability_brief": "renderer=3d"},
    )
    render_modes = [stroke for stroke in strokes if stroke.get("kind") == "setRenderMode"]
    assert render_modes, "expected at least one render mode stroke"
    assert any(stroke.get("params", {}).get("mode") == "3d" for stroke in render_modes)


def test_follow_up_adds_context_motion():
    strokes = generate_visual_strokes(
        "refresh the fish",
        context={"turn_phase": "follow-up", "entity_details": [{"id": "fish_old", "kind": "fish"}]},
    )
    follow_up_motion = [stroke for stroke in strokes if stroke.get("stroke_id") == "context-followup-motion"]
    assert follow_up_motion, "expected a follow-up motion stroke"
    assert follow_up_motion[0].get("params", {}).get("actor_id") == "fish_old"
