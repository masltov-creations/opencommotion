#!/usr/bin/env bash
set -euo pipefail

if command -v espeak >/dev/null 2>&1 || command -v espeak-ng >/dev/null 2>&1; then
  echo "Voice dependency check: espeak is already available."
  exit 0
fi

if [[ "${OPENCOMMOTION_INSTALL_SYSTEM_DEPS:-1}" != "1" ]]; then
  echo "Voice dependency check: skipped (OPENCOMMOTION_INSTALL_SYSTEM_DEPS=${OPENCOMMOTION_INSTALL_SYSTEM_DEPS})."
  exit 0
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Voice dependency check: apt-get not available; install espeak/espeak-ng manually for spoken TTS."
  exit 0
fi

echo "Voice dependency check: installing espeak-ng for spoken TTS..."

SUDO_CMD=()
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    SUDO_CMD=(sudo -n)
  elif [[ -t 0 ]] && command -v sudo >/dev/null 2>&1; then
    SUDO_CMD=(sudo)
  else
    echo "Voice dependency check: no non-interactive sudo access. Skipping auto-install."
    echo "Install manually for Linux voice: sudo apt-get update && sudo apt-get install -y espeak-ng"
    exit 0
  fi
fi

if "${SUDO_CMD[@]}" apt-get update -y && "${SUDO_CMD[@]}" apt-get install -y espeak-ng; then
  if command -v espeak >/dev/null 2>&1 || command -v espeak-ng >/dev/null 2>&1; then
    echo "Voice dependency check: espeak-ng installed successfully."
    exit 0
  fi
fi

echo "Voice dependency check: could not auto-install espeak-ng. You may still get tone fallback." >&2
echo "Install manually: sudo apt-get update && sudo apt-get install -y espeak-ng" >&2
exit 0
