from fastapi.testclient import TestClient

from services.brush_engine.opencommotion_brush.compiler import compile_brush_batch
from services.orchestrator.app.main import app


def test_orchestrate_response_shape() -> None:
    c = TestClient(app)
    res = c.post('/v1/orchestrate', json={'session_id': 't1', 'prompt': 'moonwalk chart'})
    assert res.status_code == 200
    payload = res.json()
    assert 'text' in payload
    assert 'visual_strokes' in payload
    assert 'voice' in payload
    assert 'timeline' in payload


def test_orchestrate_fish_scene_2d_and_3d_modes() -> None:
    c = TestClient(app)
    two_d = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "fish-2d",
            "prompt": "2d fish bowl scene with bubbles and caustic pattern near a window",
        },
    )
    assert two_d.status_code == 200
    two_d_kinds = {row["kind"] for row in two_d.json()["visual_strokes"]}
    assert "setRenderMode" in two_d_kinds
    assert "emitFx" in two_d_kinds

    three_d = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "fish-3d",
            "prompt": "3d fish bowl with refraction, shimmer, and volumetric mood shift",
        },
    )
    assert three_d.status_code == 200
    three_d_kinds = {row["kind"] for row in three_d.json()["visual_strokes"]}
    assert "setRenderMode" in three_d_kinds
    assert "applyMaterialFx" in three_d_kinds


def test_orchestrate_cow_moon_and_day_night_scenarios(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES", "1")
    c = TestClient(app)

    cow = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "cow-moon",
            "prompt": "A cow jumps over the moon while each word is tracked by a bouncing ball lyric cue",
        },
    )
    assert cow.status_code == 200
    cow_kinds = {row["kind"] for row in cow.json()["visual_strokes"]}
    assert "setLyricsTrack" in cow_kinds
    assert "spawnSceneActor" in cow_kinds

    day_night = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "day-night",
            "prompt": "elegant scene transition from day to night with smooth mood progression",
        },
    )
    assert day_night.status_code == 200
    day_night_kinds = {row["kind"] for row in day_night.json()["visual_strokes"]}
    assert "setEnvironmentMood" in day_night_kinds
    assert "sceneMorph" in day_night_kinds


def test_orchestrate_draw_box_prompt_generates_shape_scene() -> None:
    c = TestClient(app)
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "shape-box",
            "prompt": "draw a box",
        },
    )
    assert res.status_code == 200
    kinds = {row["kind"] for row in res.json()["visual_strokes"]}
    assert "spawnSceneActor" in kinds
    assert "spawnCharacter" not in kinds


def test_orchestrate_draw_fish_prompt_generates_fish_actor_and_no_dot_fallback() -> None:
    c = TestClient(app)
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "shape-fish",
            "prompt": "draw a fish",
        },
    )
    assert res.status_code == 200
    spawned = [row for row in res.json()["visual_strokes"] if row.get("kind") == "spawnSceneActor"]
    assert any(row.get("params", {}).get("actor_type") == "fish" for row in spawned)
    assert all(row.get("params", {}).get("actor_type") != "dot" for row in spawned)


def test_orchestrate_draw_unknown_prompt_uses_palette_script_and_compiles_to_primitives() -> None:
    c = TestClient(app)
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "shape-rocket",
            "prompt": "draw a rocket with motion",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    kinds = {row["kind"] for row in payload["visual_strokes"]}
    assert "runScreenScript" in kinds

    patches = compile_brush_batch(payload["visual_strokes"])
    actor_paths = {row["path"] for row in patches if str(row.get("path", "")).startswith("/actors/")}
    assert any(path.endswith("_sketch") for path in actor_paths)
    assert any(path.endswith("/motion") for path in {row["path"] for row in patches})
