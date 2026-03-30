#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
PID_FILE="$LOG_DIR/web.pid"
LOG_FILE="$LOG_DIR/web.log"
CONFIG_PATH="$REPO_ROOT/config/platform.example.yaml"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= | grep -F "thermo-mining serve" >/dev/null; then
    echo "web already running: $pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

nohup thermo-mining serve --config "$CONFIG_PATH" > "$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"

if kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= | grep -F "thermo-mining serve" >/dev/null; then
  echo "web started"
  exit 0
fi

rm -f "$PID_FILE"
echo "failed to start web"
exit 1
