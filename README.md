# OpenCommotion

OpenCommotion turns a prompt into a synchronized experience: text, voice, and visual animation, all in one app.

If Python had a storyboard engine, this would be it.

## Why People Care

- Show ideas as animated, narrated scenes instead of static text.
- Run autonomous agent turns with visible progress and controls.
- Save outputs as reusable artifacts for demos, teaching, and product workflows.
- Connect external agents (Codex, OpenClaw, custom clients) without building custom UI plumbing.

![OpenCommotion UI](docs/assets/opencommotion-ui.png)

## Quickstart

Prereqs:
- Python 3.11+
- Node.js 20+
- npm

One-line bootstrap (clone/update + setup):

Linux/macOS/Git Bash:

```bash
mkdir -p /home/$USER/apps && ( [ -d /home/$USER/apps/opencommotion/.git ] && git -C /home/$USER/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/opencommotion /home/$USER/apps/opencommotion ) && cd /home/$USER/apps/opencommotion && bash scripts/setup.sh
```

PowerShell (via WSL):

```powershell
wsl bash -lc 'mkdir -p ~/apps && ( [ -d ~/apps/opencommotion/.git ] && git -C ~/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/opencommotion ~/apps/opencommotion ) && cd ~/apps/opencommotion && bash scripts/setup.sh'
```

That command installs dependencies, starts the app, then opens the browser (or prompts first in interactive shells).
If browser auto-open is blocked by your environment, open manually:
- http://127.0.0.1:8000
- PowerShell: `Start-Process http://127.0.0.1:8000`
To avoid `Permission denied`, run setup via `bash scripts/setup.sh` (as shown above), not `./scripts/setup.sh`.
Setup installs an `opencommotion` launcher into `~/.local/bin`.
If `opencommotion` is not found, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

The setup panel is only shown in setup mode (`/?setup=1`) and stays hidden in normal app usage.

Manual start (if needed):

```bash
opencommotion run
```

Fast command aliases (same script, shorter typing):

```bash
opencommotion -setup
opencommotion -run
opencommotion -status
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

If you ever see `bash: ./scripts/setup.sh: Permission denied`:

```bash
cd ~/apps/opencommotion
bash scripts/setup.sh
```

## First 2 Minutes In The App

1. Open setup mode: http://127.0.0.1:8000/?setup=1
2. Choose your LLM provider and voice policy.
3. Click **Validate Setup** and **Save Setup**.
4. Enter a prompt and click **Run Turn**.
5. Watch synchronized text + voice + animation playback.
6. Save interesting results as artifacts.
7. Use **Agent Run Manager** when you want queued/autonomous runs.

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

## Codex CLI End-to-End (Step by Step)

1. Bootstrap repo and dependencies:

Linux/macOS/Git Bash:

```bash
mkdir -p /home/$USER/apps && ( [ -d /home/$USER/apps/opencommotion/.git ] && git -C /home/$USER/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/opencommotion /home/$USER/apps/opencommotion ) && cd /home/$USER/apps/opencommotion && bash scripts/setup.sh
```

PowerShell (via WSL):

```powershell
wsl bash -lc 'mkdir -p ~/apps && ( [ -d ~/apps/opencommotion/.git ] && git -C ~/apps/opencommotion pull --ff-only origin main || git clone https://github.com/masltov-creations/opencommotion ~/apps/opencommotion ) && cd ~/apps/opencommotion && bash scripts/setup.sh'
```

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

Client auth:
- HTTP header: `x-api-key: <key>`
- WebSocket: `ws://127.0.0.1:8000/v1/events/ws?api_key=<key>`

LLM providers:
- `heuristic|ollama|openai-compatible|codex-cli|openclaw-cli|openclaw-openai`

Voice engines:
- STT: `auto|faster-whisper|vosk|openai-compatible|text-fallback`
- TTS: `auto|piper|espeak|openai-compatible|tone-fallback`

## Diagnostics

```bash
opencommotion status
opencommotion preflight
opencommotion doctor
```

## Core API Surface

- `GET /v1/setup/state`
- `POST /v1/setup/validate`
- `POST /v1/setup/state`
- `POST /v1/agent-runs`
- `GET /v1/agent-runs`
- `GET /v1/agent-runs/{run_id}`
- `POST /v1/agent-runs/{run_id}/enqueue`
- `POST /v1/agent-runs/{run_id}/control`

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
