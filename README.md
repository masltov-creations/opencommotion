# OpenCommotion

OpenCommotion is a prompt-to-scene engine: it takes a prompt and produces synchronized text, voice, and animated visuals in one UI.

Imagine having an AI agent that can both explain and show you an answer at the same time. That is OpenCommotion.

Project name: `OpenCommotion`.

If Python and a storyboard had a very productive meeting, this would be the output.

## Why People Care

- Show ideas as animated, narrated scenes instead of static text.
- Run autonomous agent turns with visible progress and controls.
- Save outputs as reusable artifacts for demos, teaching, and product workflows.
- Connect external agents (Codex, OpenClaw, custom clients) without building custom UI plumbing.
- Get from clone to first working turn quickly, without bespoke local scripts.

![OpenCommotion UI](docs/assets/opencommotion-ui.png)

## Quickstart (And Now For Something Completely Practical)

Prereqs:
- Python 3.11+
- Node.js 20+
- npm

One-line bootstrap (clone/update + setup):

Linux/macOS/Git Bash/WSL shell:

```bash
mkdir -p /home/$USER/apps && ( [ -d /home/$USER/apps/opencommotion/.git ] && git -C /home/$USER/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/OpenCommotion /home/$USER/apps/opencommotion ) && cd /home/$USER/apps/opencommotion && bash scripts/setup.sh
```

PowerShell (calls into WSL):

```powershell
wsl bash -lc 'mkdir -p ~/apps && ( [ -d ~/apps/opencommotion/.git ] && git -C ~/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/OpenCommotion ~/apps/opencommotion ) && cd ~/apps/opencommotion && bash scripts/setup.sh'
```

Important shell rule:
- If your prompt looks like `mashuri@...$`, you are already in WSL. Run Linux commands directly and do not prefix with `wsl`.
- Only use `wsl bash -lc '...'` from Windows PowerShell/CMD.

That command installs dependencies, starts the app, and opens the browser (or asks first in interactive shells).
If browser auto-open is blocked by your environment, open manually:
- http://127.0.0.1:8000
- PowerShell: `Start-Process http://127.0.0.1:8000`
To avoid `Permission denied`, run setup via `bash scripts/setup.sh` (as shown above), not `./scripts/setup.sh`.
Setup installs an `opencommotion` launcher into `~/.local/bin`.
On Windows + WSL, setup also installs `opencommotion.cmd` into `%USERPROFILE%\.local\bin` and adds it to user PATH if needed.
If this is your first install, restart PowerShell once so `opencommotion` is recognized.
If `opencommotion` is not found, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

PowerShell fallback if PATH has not refreshed yet:

```powershell
& "$env:USERPROFILE\.local\bin\opencommotion.cmd" -status
```

The setup panel appears only in setup mode (`/?setup=1`) and stays hidden in normal app usage.

Manual start (if needed):

```bash
opencommotion run
```

Fast command aliases (same script, shorter typing):

```bash
opencommotion -setup
opencommotion -run
opencommotion -status
opencommotion -fresh
opencommotion -stop
```

PowerShell equivalent:

```powershell
opencommotion -setup
opencommotion -run
opencommotion -status
opencommotion -stop
```

Open the app:
- http://127.0.0.1:8000

Stop the app:

```bash
opencommotion down
```

If startup fails due to a port conflict, the script now exits with a clear error.
Common recovery path:

```bash
opencommotion down
opencommotion run
```

If the UI loads but prompts look stale or turns behave inconsistently after moving/cloning repos, run:

```bash
opencommotion fresh
```

This resets local runtime state and rebuilds UI assets from current source.

If you see `orchestrate failed: request timed out or was aborted` on longer prompts, increase UI request timeout and restart:

```bash
echo 'VITE_ORCHESTRATE_TIMEOUT_MS=180000' >> .env
opencommotion run
```

If you still see the old error text `signal is aborted without reason`, you are on an older UI build/launcher.
Run this recovery sequence, then hard-refresh the browser (`Ctrl+Shift+R`):

```bash
opencommotion where
opencommotion version
opencommotion update
opencommotion run
```

If you ever see `bash: ./scripts/setup.sh: Permission denied`:

```bash
cd ~/apps/opencommotion
bash scripts/setup.sh
```

If you see `vite: Permission denied` during setup/run in WSL, update and retry first:

```bash
git pull --ff-only origin main
bash scripts/setup.sh
```

If it still fails on an older checkout:

```bash
chmod +x node_modules/.bin/vite apps/ui/node_modules/.bin/vite 2>/dev/null || true
opencommotion -run
```

## First 2 Minutes In The App

1. Open setup mode: http://127.0.0.1:8000/?setup=1
2. Choose your LLM provider and voice policy.
3. Click **Validate Setup** and **Save Setup**.
4. Enter a prompt and click **Run Turn**.
   - Example stretch prompt: `Create a serene cinematic scene of a goldfish swimming inside a clear glass fish bowl on a wooden desk near a window, with bubbles, caustic light, and a day-to-dusk mood shift.`
5. Watch synchronized text + voice + animation playback.
If backend voice engine is unavailable, the UI automatically falls back to browser speech so narration still works.
6. Save interesting results as artifacts.
7. Use **Agent Run Manager** when you want queued/autonomous runs.

If this worked, congratulations: your application is now less “science project” and more “usable product”.

## Daily Use

Start:

```bash
opencommotion run
```

Check health:

```bash
opencommotion status
```

Stop:

```bash
opencommotion down
```

Start fresh (clean local reset + reinstall + run):

```bash
opencommotion fresh
```

Optional fresh flags via env vars:
- `OPENCOMMOTION_FRESH_RESET_ENV=1 opencommotion fresh` (also resets `.env`)
- `OPENCOMMOTION_FRESH_KEEP_BUNDLES=1 opencommotion fresh` (keeps artifact bundles)
- `OPENCOMMOTION_FRESH_DRY_RUN=1 opencommotion fresh` (preview only)

Update safely (works even if stack is already running):

```bash
opencommotion update
```

`opencommotion update` will:
1. detect if the stack is running
2. stop it if needed
3. `git pull --ff-only origin main`
4. reinstall/update dependencies
5. restart automatically only if it was running before

## Connect Your Agents (Python-first)

Robust default client:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/robust_turn_client.py \
  --session demo-1 \
  --prompt "moonwalk adoption chart with synchronized narration"
```

Codex/OpenClaw examples:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/codex_cli_turn_client.py
python3 scripts/agent_examples/openclaw_cli_turn_client.py
python3 scripts/agent_examples/openclaw_openai_turn_client.py --base-url http://127.0.0.1:8002/v1
```

REST + WebSocket baseline example:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/rest_ws_agent_client.py \
  --session demo-2 \
  --prompt "ufo landing with pie chart"
```

Visual-intelligence scenario requirements and certification matrix:
- `docs/VISUAL_INTELLIGENCE_PLAN.md`
- Includes common graph mistakes + hardening rules and compatibility checks.
- Tool-gap tracking lives in `docs/TOOL_ENHANCEMENT_BACKLOG.md`.

## Codex CLI End-to-End (Step by Step)

1. Bootstrap repo and dependencies:

Linux/macOS/Git Bash/WSL shell:

```bash
mkdir -p /home/$USER/apps && ( [ -d /home/$USER/apps/opencommotion/.git ] && git -C /home/$USER/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/OpenCommotion /home/$USER/apps/opencommotion ) && cd /home/$USER/apps/opencommotion && bash scripts/setup.sh
```

PowerShell (calls into WSL):

```powershell
wsl bash -lc 'mkdir -p ~/apps && ( [ -d ~/apps/opencommotion/.git ] && git -C ~/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/OpenCommotion ~/apps/opencommotion ) && cd ~/apps/opencommotion && bash scripts/setup.sh'
```

If you are already in a WSL shell (`user@host:~$`), do not run the `wsl ...` wrapper.

2. Authenticate Codex CLI once:

```bash
codex login
```

3. Verify Codex CLI and app status:

```bash
opencommotion doctor
opencommotion status
codex --version
```

4. If app is not running, start it:

```bash
opencommotion run
```

5. Configure Codex provider in the app:
   - Open http://127.0.0.1:8000/?setup=1
   - Setup Wizard -> provider: `codex-cli`
   - Binary: `codex` (or absolute path)
   - Voice policy: for first test, keep strict real-engine mode off unless your TTS engine is fully configured
   - Optional model: set if you want non-default behavior
   - Click **Validate Setup** and **Save Setup**

6. Run a turn in the UI:
   - Enter a prompt
   - Click **Run Turn**
   - Confirm text + voice + animation are produced

7. Run the same flow from Python client:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/codex_cli_turn_client.py \
  --session codex-e2e \
  --prompt "show an adoption chart with synchronized narration"
```

8. Optional: run Codex through autonomous queue controls:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/agent-runs \
  -H "x-api-key: dev-opencommotion-key" \
  -H "content-type: application/json" \
  -d '{"label":"codex-run","auto_run":true}'
```

Then enqueue prompts from the UI (**Agent Run Manager**) or API:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/agent-runs/<run_id>/enqueue \
  -H "x-api-key: dev-opencommotion-key" \
  -H "content-type: application/json" \
  -d '{"prompt":"animate moonwalk progression with narration"}'
```

9. Stop services when done:

```bash
opencommotion down
```

Headless/CI note:
- Use `bash scripts/setup.sh --no-run` if you want setup without starting services.
- Use `bash scripts/setup.sh --no-open` if you want startup without browser prompt.
- Use `bash scripts/setup.sh --with-cli-setup` if you want to run terminal setup wizard before startup.

## Defaults You Should Know

Auth defaults:
- `OPENCOMMOTION_AUTH_MODE=api-key`
- `OPENCOMMOTION_API_KEYS=dev-opencommotion-key`
- `OPENCOMMOTION_ALLOWED_IPS=127.0.0.1/32,::1/128` (local-machine-only default for `network-trust`)
- In `network-trust` mode, do not leave `OPENCOMMOTION_ALLOWED_IPS` empty unless you intentionally want all IPs allowed.

Client auth:
- HTTP header: `x-api-key: <key>`
- WebSocket: `ws://127.0.0.1:8000/v2/events/ws?api_key=<key>`

LLM providers:
- `heuristic|ollama|openai-compatible|codex-cli|openclaw-cli|openclaw-openai`

Voice engines:
- STT: `auto|faster-whisper|vosk|openai-compatible|text-fallback`
- TTS: `auto|piper|espeak|openai-compatible|tone-fallback`
- On Windows/WSL with `auto`, backend also attempts Windows SAPI before tone fallback.

## Diagnostics

```bash
opencommotion status
opencommotion preflight
opencommotion doctor
python3 scripts/evaluate_market_graph.py
python3 scripts/evaluate_market_graph.py --inprocess
python3 scripts/prompt_compat_probe.py --inprocess --seed 23
```

`prompt_compat_probe.py` exits non-zero when required scenario expectations fail; use that as a triage gate.
Use probe output + `docs/TOOL_ENHANCEMENT_BACKLOG.md` to record bug candidates vs enhancement candidates from random prompts.

## Core API Surface

- `POST /v2/orchestrate`
- `GET /v2/runtime/capabilities`
- `WS /v2/events/ws`
- `GET /v2/scenes/{scene_id}`
- `POST /v2/scenes/{scene_id}/snapshot`
- `POST /v2/scenes/{scene_id}/restore`
- `GET /v1/setup/state`
- `POST /v1/setup/validate`
- `POST /v1/setup/state`
- `POST /v1/agent-runs`
- `GET /v1/agent-runs`
- `GET /v1/agent-runs/{run_id}`
- `POST /v1/agent-runs/{run_id}/enqueue`
- `POST /v1/agent-runs/{run_id}/control`

For market-growth prompts, `POST /v2/orchestrate` returns `quality_report` compatibility checks for generated graph payloads.
`/v1/*` endpoints remain as a compatibility shim for one release and emit deprecation/sunset headers.

WebSocket run events:
- `agent.run.state`
- `agent.turn.started`
- `agent.turn.completed`
- `agent.turn.failed`

## Production Deployment

Use:
- `docker-compose.prod.yml`
- `docker/Dockerfile.gateway`
- `docker/Dockerfile.orchestrator`
- `deploy/nginx/opencommotion.conf`
- `deploy/prometheus/*`
- `deploy/grafana/*`

Deploy:
1. Copy `.env.example` to `.env` and set production values.
2. Put TLS certs in `deploy/nginx/certs/` (`fullchain.pem`, `privkey.pem`).
3. Run `docker compose -f docker-compose.prod.yml up -d --build`.

## Backup And Restore

```bash
bash scripts/backup_runtime.sh
bash scripts/restore_runtime.sh <backup-tar.gz>
```

Backs up:
- `data/artifacts/artifacts.db`
- `data/artifacts/bundles/`
- `runtime/agent-runs/agent_manager.db`

## Validation Gates

```bash
opencommotion test
opencommotion test-ui
opencommotion test-e2e
opencommotion test-complete
opencommotion fresh-agent-e2e
```

## Plan Tracking

- Authoritative implementation plan and status tracker: `PROJECT.md`
- Supporting plan docs:
  - `docs/VISUAL_INTELLIGENCE_PLAN.md`
  - `docs/TOOL_ENHANCEMENT_BACKLOG.md`
- Update expectation: keep `PROJECT.md` current on every implementation session; do not mark work complete without evidence.

## Extend It

- Gateway APIs and run manager: `services/gateway/app/main.py`
- Orchestrator: `services/orchestrator/app/main.py`
- LLM adapters: `services/agents/text/adapters.py`
- Voice engines: `services/agents/voice/stt/worker.py`, `services/agents/voice/tts/worker.py`
- UI runtime and wizard: `apps/ui/src/App.tsx`

## More Documentation

- `docs/AGENT_CONNECTION.md`
- `docs/USAGE_PATTERNS.md`
- `docs/ARCHITECTURE.md`
- `PROJECT.md`
- `RELEASE.md`
