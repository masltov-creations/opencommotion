# Contributing to OpenCommotion

## Branch and commit workflow

1. Create a focused branch from `main`.
2. Keep changes scoped to one concern (runtime, protocol, docs, tests, etc.).
3. Run required local gates before opening a PR.
4. Use descriptive commit messages with explicit behavior changes.

## Required local gates before PR

```bash
make test-all
make test-e2e
make security-checks
make perf-checks
```

For end-user workflow confidence:

```bash
make fresh-agent-e2e
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
- [ ] `make test-complete` passes
- [ ] `make fresh-agent-e2e` passes
- [ ] Documentation updated where applicable
