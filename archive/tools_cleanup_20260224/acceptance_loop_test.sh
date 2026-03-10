#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$HOME/BotA"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

bash "$ROOT/tools/run_loop.sh" once
echo "---- tail loop.log ----"
tail -n 40 "$LOGS/loop.log" || true
echo "---- recent signal jsons ----"
ls -1t "$LOGS"/signal_* 2>/dev/null | head -n 4 | xargs -r -I{} sh -c 'echo "= {}"; tail -n +1 "{}" 2>/dev/null | head -n 5'
