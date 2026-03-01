#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

detect_app_url() {
  local host="127.0.0.1"
  if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    local wsl_ip
    wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -n "$wsl_ip" ]]; then
      host="$wsl_ip"
    fi
  fi
  echo "http://$host:8000"
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

bash scripts/install_voice_deps.sh
python scripts/configure_voice_defaults.py
bash scripts/install_launcher.sh
if ! bash scripts/install_windows_shim.sh; then
  echo "Windows launcher install skipped. You can still run from WSL with: opencommotion -run"
fi

echo "Install complete."
echo "Next steps:"
echo "  1) opencommotion -setup"
echo "  2) opencommotion -run"
echo "  3) open $(detect_app_url)"
