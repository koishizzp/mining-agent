#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
PID_FILE="$LOG_DIR/web.pid"
CONFIG_PATH="$REPO_ROOT/config/platform.example.yaml"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= | grep -F "thermo-mining serve" >/dev/null; then
    echo "web running: $pid"
  else
    rm -f "$PID_FILE"
    echo "web not running"
  fi
else
  echo "web not running"
fi

thermo-mining serve --config "$CONFIG_PATH" --help >/dev/null
