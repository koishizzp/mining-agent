#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs
nohup thermo-mining serve --config config/platform.example.yaml > logs/web.log 2>&1 &
echo $! > logs/web.pid
echo "web started"
