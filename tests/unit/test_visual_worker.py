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
