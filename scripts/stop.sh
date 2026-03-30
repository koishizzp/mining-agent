#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
PID_FILE="$LOG_DIR/web.pid"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= | grep -F "thermo-mining serve" >/dev/null; then
    kill "$pid"
  fi
  rm -f "$PID_FILE"
fi

echo "web stopped"
