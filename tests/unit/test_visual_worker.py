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


def test_market_growth_prompt_includes_segmented_attach_chart() -> None:
    strokes = generate_visual_strokes(
        "animated presentation showcasing market growth and increases in segmented attach within certain markets"
    )
    kinds = {row["kind"] for row in strokes}
    assert "drawAdoptionCurve" in kinds
    assert "drawSegmentedAttachBars" in kinds


def test_cow_moon_lyric_prompt_includes_lyrics_and_bounce() -> None:
    strokes = generate_visual_strokes(
        "A cow jumps over the moon while the phrase appears with a bouncing ball synced to each word"
    )
    kinds = {row["kind"] for row in strokes}
    assert "spawnSceneActor" in kinds
    assert "setLyricsTrack" in kinds
    assert "emitFx" in kinds


def test_day_night_prompt_includes_environment_and_transition() -> None:
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
