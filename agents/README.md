# Expert Agents

Agent specs define tuned roles for parallel delivery.

Run `python3 scripts/spawn_expert_agents.py` to initialize runtime state files.
Run `python3 scripts/init_wave_context.py --run-id <wave-id>` to initialize `current-wave-context.json` and `lane-ownership.json`.

Implementation skill scaffolds are in `agents/scaffolds/`.
- Start with `agents/scaffolds/skill-agent-orchestration-ops.json` for shared context + coordination protocol.
- Use `agents/scaffolds/templates/` for wave context, lane ownership, and handoff report records.

For connecting external agent clients to runtime APIs/events, use:
- `docs/USAGE_PATTERNS.md` (recommended default operating model)
- `docs/AGENT_CONNECTION.md`
- `scripts/agent_examples/robust_turn_client.py` (robust default client)
- `scripts/agent_examples/rest_ws_agent_client.py`
