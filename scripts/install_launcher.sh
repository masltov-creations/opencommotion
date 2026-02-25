#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${OPENCOMMOTION_BIN_DIR:-$HOME/.local/bin}"
TARGET_PATH="$TARGET_DIR/opencommotion"

mkdir -p "$TARGET_DIR"
chmod +x "$ROOT/opencommotion"

if ln -sfn "$ROOT/opencommotion" "$TARGET_PATH" 2>/dev/null; then
  :
else
  cp "$ROOT/opencommotion" "$TARGET_PATH"
  chmod +x "$TARGET_PATH"
fi

echo "Installed launcher: $TARGET_PATH"
case ":$PATH:" in
  *":$TARGET_DIR:"*)
    echo "Launcher is on PATH. Run: opencommotion -status"
    ;;
  *)
    echo "Add launcher dir to PATH:"
    echo "  export PATH=\"$TARGET_DIR:\$PATH\""
    ;;
esac

