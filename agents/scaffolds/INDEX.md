# Closeout Skill Scaffolds

Use these scaffold files to run the final implementation wave in parallel with clear ownership and gates.

## Recommended execution order

1. `skill-agent-orchestration-ops.json`
2. `skill-schema-validation.json`
3. `skill-voice-production.json`
4. `skill-ui-patch-runtime.json`
5. `skill-artifact-semantic-recall.json`
6. `skill-e2e-realtime.json`
7. `skill-security-ops.json`
8. `skill-release-docs.json`

## Notes

- Each scaffold includes objective, dependencies, implementation checklist, validation commands, acceptance criteria, and handoff artifacts.
- Keep changes scoped per scaffold branch and merge only after checklist + validation pass.
- Coordination templates are in `agents/scaffolds/templates/` (`wave-context`, `lane-ownership`, `handoff-report`).
