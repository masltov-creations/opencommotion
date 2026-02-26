# Contributing to OpenCommotion

## Branch and commit workflow

1. Create a focused branch from `main`.
2. Keep changes scoped to one concern (runtime, protocol, docs, tests, etc.).
3. Run required local gates before opening a PR.
4. Keep `PROJECT.md` current in every implementation session.
5. Use descriptive commit messages with explicit behavior changes.

## Required plan tracking (interrupt-safe)

If you changed implementation files, you must update `PROJECT.md` in the same branch/session:

1. Update `Updated:` to the current date.
2. Update `Current status`.
3. Update `Progress checklist` accurately.
4. Update `Active tasks` with:
   - planned
   - done
   - in progress/not finished
   - remaining
5. Append a `Change log` line with concrete evidence (test command, validation command, or artifact path).

CI enforces this with `scripts/check_project_plan_sync.py`.

## Required local gates before PR

```bash
python3 scripts/opencommotion.py test
python3 scripts/opencommotion.py test-ui
python3 scripts/opencommotion.py test-e2e
python3 scripts/opencommotion.py doctor
```

For full end-user workflow confidence:

```bash
python3 scripts/opencommotion.py test-complete
python3 scripts/opencommotion.py fresh-agent-e2e
```

## Quality standards

- Do not break protocol contracts without versioning updates.
- Preserve deterministic visual patch behavior (`at_ms` ordering).
- Keep error envelopes stable for client integrations.
- Add/adjust tests with every behavior change.
- Update docs for any public interface or workflow change.

## PR checklist

- [ ] Feature/bug behavior clearly described
- [ ] Tests added or updated
- [ ] `PROJECT.md` updated with accurate status and change log evidence
- [ ] `python3 scripts/opencommotion.py test-complete` passes
- [ ] `python3 scripts/opencommotion.py fresh-agent-e2e` passes
- [ ] Documentation updated where applicable
