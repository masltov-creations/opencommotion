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


def test_orchestrate_fish_and_bubble_prompt_routes_to_script_pipeline() -> None:
    c = TestClient(app)
    # Fish/bubble prompts now route through LLM → entity → palette fallback, not pre-canned scenes
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "fish-script",
            "prompt": "fish swimming in a bowl with bubbles",
        },
    )
    assert res.status_code == 200
    kinds = {row["kind"] for row in res.json()["visual_strokes"]}
    assert "runScreenScript" in kinds or "annotateInsight" in kinds
    # Pre-canned bowl/caustic actors must be absent
    spawned = [row for row in res.json()["visual_strokes"] if row.get("kind") == "spawnSceneActor"]
    assert all(row.get("params", {}).get("actor_id") not in {"fish_bowl", "plant_a"} for row in spawned)


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


def test_orchestrate_draw_fish_prompt_routes_to_script_pipeline() -> None:
    # "draw a fish" now routes through LLM/entity/palette — no pre-canned fish actor
    c = TestClient(app)
    res = c.post(
        "/v1/orchestrate",
        json={
            "session_id": "shape-fish",
            "prompt": "draw a fish",
        },
    )
    assert res.status_code == 200
    kinds = {row["kind"] for row in res.json()["visual_strokes"]}
    assert "runScreenScript" in kinds
    # Pre-canned fish_1 actor must not be present
    spawned = [row for row in res.json()["visual_strokes"] if row.get("kind") == "spawnSceneActor"]
    assert all(row.get("params", {}).get("actor_id") not in {"fish_1", "goldfish"} for row in spawned)


def test_orchestrate_draw_unknown_prompt_uses_palette_script_and_compiles_to_primitives() -> None:
    # "draw a rocket with motion" now routes to entity decomposition (not seeded palette script),
    # producing named shape actors (e.g. rocket_body, rocket_nose_cone) and a motion patch.
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
    # Entity decomposition route: actor paths exist (any name, not restricted to _sketch)
    assert actor_paths, "Expected compiled actor paths from entity decomposition"
    assert any(path.endswith("/motion") for path in {row["path"] for row in patches})
