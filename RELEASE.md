# OpenCommotion Release Runbook

This runbook defines the release-candidate path on a clean machine.

## 1) Prerequisites

- Python 3.11+
- Node.js 20+
- npm
- `curl`
- `apt-get` (for user-mode Playwright dependency fetch in Linux environments)

## 2) Clean setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
```

## 3) Validate core stack

```bash
make dev
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
make down
```

## 4) Run full quality gates

```bash
make test-complete
```

Includes:
- backend + integration tests
- UI tests
- browser E2E
- security checks (`pip check`, `pip-audit`, API baseline tests, `npm audit`)
- performance checks (orchestrate latency + UI patch runtime threshold tests)

## 5) Fresh agent consumer E2E proof

```bash
make fresh-agent-e2e
```

This command:
1. Bootstraps dependencies from scratch (venv + npm),
2. Starts local stack,
3. Launches robust agent client,
4. Verifies output contract (`turn_id`, `patch_count`, `text`, `voice_uri`),
5. Shuts down stack.

## 6) Release-candidate completion criteria

- `make test-complete` passes
- `make fresh-agent-e2e` passes
- `README.md`, `docs/AGENT_CONNECTION.md`, `docs/USAGE_PATTERNS.md`, and `docs/ARCHITECTURE.md` are aligned with behavior
- `docs/CLOSEOUT_PLAN.md` status snapshot shows all completion gates checked

## 7) Suggested release tag flow

```bash
git checkout main
git pull --ff-only
make test-complete
make fresh-agent-e2e
git tag -a v0.5.0-rc1 -m "OpenCommotion release candidate 1"
git push origin main --tags
```
