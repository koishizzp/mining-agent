#!/usr/bin/env bash
set -euo pipefail

if [[ -f logs/web.pid ]]; then
  kill "$(cat logs/web.pid)"
  rm -f logs/web.pid
fi

echo "web stopped"
