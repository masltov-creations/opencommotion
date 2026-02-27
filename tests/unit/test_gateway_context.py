from services.gateway.app import main


def test_build_context_first_turn():
    main._reset_session_context_cache()
    context = main._build_orchestrate_context(session_id="session-1", prompt="start", source="api")
    assert context["turn_phase"] == "first-turn"
    assert "session=session-1" in context["scene_brief"]
    assert context["entity_details"] == []
    assert context["capability_brief"].startswith("source=api")


def test_context_updates_and_follow_up():
    main._reset_session_context_cache()
    _ = main._build_orchestrate_context(session_id="session-2", prompt="start", source="agent-run")
    main._update_session_context(
        session_id="session-2",
        prompt="start",
        strokes=[
            {"kind": "spawnCharacter", "params": {"actor_id": "fish_actor"}},
            {"kind": "setActorMotion", "params": {"actor_id": "fish_actor"}},
        ],
        source="agent-run",
    )
    follow_up = main._build_orchestrate_context(session_id="session-2", prompt="next", source="agent-run")
    assert follow_up["turn_phase"] == "follow-up"
    assert follow_up["entity_details"] and follow_up["entity_details"][0]["id"] == "fish_actor"


def test_context_includes_reminder_override():
    main._reset_session_context_cache()
    reminder_context = main._build_orchestrate_context(
        session_id="session-3",
        prompt="start",
        source="api",
        reminder_prompt="urgency reminder",
    )
    assert reminder_context.get("system_prompt_override") == "urgency reminder"
