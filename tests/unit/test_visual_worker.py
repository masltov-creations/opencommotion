from __future__ import annotations

from services.agents.visual.worker import generate_visual_strokes


def test_fish_prompt_generates_base_scene_primitives() -> None:
    strokes = generate_visual_strokes("a fish swimming in a fish bowl with bubbles and caustic desk lighting")
    kinds = {row["kind"] for row in strokes}
    assert "setRenderMode" in kinds
    assert "spawnSceneActor" in kinds
    assert "setActorMotion" in kinds
    assert "emitFx" in kinds
    assert "setEnvironmentMood" in kinds


def test_fish_prompt_3d_includes_material_fx() -> None:
    strokes = generate_visual_strokes("3d fish bowl cinematic with refraction and volumetric light")
    kinds = [row["kind"] for row in strokes]
    assert "setRenderMode" in kinds
    assert "applyMaterialFx" in kinds


def test_fish_prompt_3_dfishbowl_uses_constituent_3d_scene() -> None:
    strokes = generate_visual_strokes("3 dfishbowl cinematic with bubbles and caustic refraction")
    kinds = [row["kind"] for row in strokes]
    assert "spawnSceneActor" in kinds
    assert "setActorMotion" in kinds
    assert "emitFx" in kinds
    assert "applyMaterialFx" in kinds
    assert "runScreenScript" not in kinds

    render_mode = next(row for row in strokes if row["kind"] == "setRenderMode")
    assert render_mode.get("params", {}).get("mode") == "3d"


def test_market_growth_prompt_includes_segmented_attach_chart(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES", "1")
    strokes = generate_visual_strokes(
        "animated presentation showcasing market growth and increases in segmented attach within certain markets"
    )
    kinds = {row["kind"] for row in strokes}
    assert "drawAdoptionCurve" in kinds
    assert "drawSegmentedAttachBars" in kinds


def test_cow_moon_lyric_prompt_includes_lyrics_and_bounce(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES", "1")
    strokes = generate_visual_strokes(
        "A cow jumps over the moon while the phrase appears with a bouncing ball synced to each word"
    )
    kinds = {row["kind"] for row in strokes}
    assert "spawnSceneActor" in kinds
    assert "setLyricsTrack" in kinds
    assert "emitFx" in kinds


def test_day_night_prompt_includes_environment_and_transition(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES", "1")
    strokes = generate_visual_strokes("elegant transition from day to night with smooth scene progression")
    kinds = {row["kind"] for row in strokes}
    assert "setEnvironmentMood" in kinds
    assert "sceneMorph" in kinds


def test_draw_box_prompt_generates_shape_actor_without_v1_guide_default() -> None:
    strokes = generate_visual_strokes("draw a box")
    kinds = {row["kind"] for row in strokes}
    assert "spawnSceneActor" in kinds
    assert "spawnCharacter" not in kinds
    spawned = [row for row in strokes if row["kind"] == "spawnSceneActor"]
    assert any(row.get("params", {}).get("actor_type") in {"box", "square", "rectangle"} for row in spawned)


def test_black_fish_square_bowl_prompt_uses_prompt_style() -> None:
    strokes = generate_visual_strokes("show a black fish in a square bowl")
    spawned = [row for row in strokes if row["kind"] == "spawnSceneActor"]
    bowl = next(row for row in spawned if row.get("params", {}).get("actor_id") == "fish_bowl")
    fish = next(row for row in spawned if row.get("params", {}).get("actor_id") == "goldfish")
    assert bowl["params"]["style"]["shape"] == "square"
    assert fish["params"]["style"]["fill"] == "#111827"


def test_draw_fish_prompt_generates_fish_actor_and_not_dot_fallback() -> None:
    strokes = generate_visual_strokes("draw a fish")
    spawned = [row for row in strokes if row["kind"] == "spawnSceneActor"]
    assert any(row.get("params", {}).get("actor_type") == "fish" for row in spawned)
    assert all(row.get("params", {}).get("actor_type") != "dot" for row in spawned)


def test_bouncing_ball_prompt_respects_requested_quantity() -> None:
    strokes = generate_visual_strokes("show 2 bouncing balls")
    spawned = [row for row in strokes if row["kind"] == "spawnSceneActor"]
    balls = [row for row in spawned if row.get("params", {}).get("actor_type") == "circle"]
    assert len(balls) == 2
    actor_ids = {row.get("params", {}).get("actor_id") for row in balls}
    assert actor_ids == {"ball_1", "ball_2"}

    motions = [row for row in strokes if row["kind"] == "setActorMotion"]
    motion_ids = {row.get("params", {}).get("actor_id") for row in motions}
    assert {"ball_1", "ball_2"}.issubset(motion_ids)


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
    assert "Interface primitives route" in str(note.get("params", {}).get("text", ""))


def test_draw_prompt_with_relative_xyz_points_uses_script_points() -> None:
    strokes = generate_visual_strokes("draw shape points 0.2,0.3,0.1 0.6,0.3,0.2 0.8,0.7,0.3 and animate")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    polyline = next(cmd for cmd in commands if cmd.get("op") == "polyline")
    assert polyline["relative"] is True
    assert len(polyline["points"]) == 3
