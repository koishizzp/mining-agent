#!/usr/bin/env bash
set -euo pipefail

if [[ -f logs/web.pid ]]; then
  echo "web pid: $(cat logs/web.pid)"
else
  echo "web not running"
fi

thermo-mining serve --help >/dev/null
