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
nohup thermo-mining serve --config "$CONFIG_PATH" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "web started"
