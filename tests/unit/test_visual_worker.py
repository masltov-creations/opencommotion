from __future__ import annotations

from services.agents.visual.worker import generate_visual_strokes


def test_draw_box_prompt_generates_shape_actor_without_v1_guide_default() -> None:
    strokes = generate_visual_strokes("draw a box")
    kinds = {row["kind"] for row in strokes}
    assert "spawnSceneActor" in kinds
    assert "spawnCharacter" not in kinds
    spawned = [row for row in strokes if row["kind"] == "spawnSceneActor"]
    assert any(row.get("params", {}).get("actor_type") in {"box", "square", "rectangle"} for row in spawned)


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


# ---------------------------------------------------------------------------
# Entity decomposition tests
# ---------------------------------------------------------------------------

def test_entity_decomposition_house_builds_rect_and_polygon() -> None:
    strokes = generate_visual_strokes("draw a house")
    kinds = {row["kind"] for row in strokes}
    assert "runScreenScript" in kinds
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ops = {cmd["op"] for cmd in commands}
    assert "rect" in ops            # walls, door, windows
    assert "polygon" in ops         # roof
    ids = {cmd.get("id") for cmd in commands}
    assert "house_walls" in ids
    assert "house_roof" in ids
    assert "house_door" in ids


def test_entity_decomposition_cloud_uses_ellipse_ops() -> None:
    strokes = generate_visual_strokes("draw a cloud")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ellipses = [cmd for cmd in commands if cmd["op"] == "ellipse"]
    assert len(ellipses) == 3
    ids = {cmd["id"] for cmd in ellipses}
    assert ids == {"cloud_main", "cloud_l", "cloud_r"}


def test_entity_decomposition_moon_has_crescent_shadow() -> None:
    strokes = generate_visual_strokes("show the moon")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ids = {cmd.get("id") for cmd in commands}
    assert "moon_body" in ids
    assert "moon_shadow" in ids   # dark overlay circle creates crescent
    assert "moon_crater_1" in ids


def test_entity_decomposition_sunset_has_sun_and_wave() -> None:
    strokes = generate_visual_strokes("draw a sunset")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ids = {cmd.get("id") for cmd in commands}
    assert "sunset_sun" in ids
    assert "sunset_horizon" in ids
    assert "sunset_wave_1" in ids


def test_entity_decomposition_planet_has_fill_none_ring() -> None:
    strokes = generate_visual_strokes("draw a planet")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ring = next(cmd for cmd in commands if cmd.get("id") == "planet_ring")
    assert ring["op"] == "ellipse"
    assert ring["fill"] == "none"   # ring rendered as outline only


def test_entity_decomposition_boat_with_motion_has_move_op() -> None:
    strokes = generate_visual_strokes("draw a boat with motion")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    move_cmds = [cmd for cmd in commands if cmd.get("op") == "move"]
    assert move_cmds, "expected a move op for animated boat"
    assert move_cmds[0]["target_id"] == "boat_hull"
    assert move_cmds[0]["loop"] is True


def test_entity_alias_spaceship_matches_rocket_template() -> None:
    strokes = generate_visual_strokes("draw a spaceship")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    ids = {cmd.get("id") for cmd in commands}
    assert "rocket_body" in ids
    assert "rocket_nose" in ids


def test_entity_alias_ocean_matches_wave_template() -> None:
    strokes = generate_visual_strokes("show the ocean")
    script = next(row for row in strokes if row["kind"] == "runScreenScript")
    commands = script["params"]["program"]["commands"]
    polylines = [cmd for cmd in commands if cmd["op"] == "polyline"]
    assert len(polylines) >= 2
    ids = {cmd["id"] for cmd in polylines}
    assert "wave_1" in ids


def test_entity_annotation_contains_primitives_route_label() -> None:
    strokes = generate_visual_strokes("draw a butterfly")
    note = next(row for row in strokes if row["kind"] == "annotateInsight" and
                "Interface primitives route" in str(row.get("params", {}).get("text", "")))
    assert "butterfly" in note["params"]["text"]


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
