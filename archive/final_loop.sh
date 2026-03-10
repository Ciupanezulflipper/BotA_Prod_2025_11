#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$HOME/bot-a"
CADENCE_MIN="${CADENCE_MIN:-15}"

while true; do
  date -u +"[final_loop] %Y-%m-%d %H:%M UTC :: tick"
  python "$HOME/bot-a/tools/final_runner.py"
  sleep "$((CADENCE_MIN*60))"
done
