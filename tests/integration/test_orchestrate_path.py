from fastapi.testclient import TestClient

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


def test_orchestrate_cow_moon_and_day_night_scenarios() -> None:
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
