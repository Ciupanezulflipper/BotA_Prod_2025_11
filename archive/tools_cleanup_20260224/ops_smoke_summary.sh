#!/usr/bin/env bash
set -euo pipefail
ROOT="${BOTA_ROOT:-$HOME/BotA}"
bash "$ROOT/tools/daily_accuracy_summary.sh"
echo "---- tail daily_summary.log ----"
tail -n 40 "$ROOT/logs/daily_summary.log" || true
