#!/usr/bin/env bash
set -euo pipefail
ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOG="${ROOT}/logs/cron.accuracy.log"
mkdir -p "${ROOT}/logs"
ts(){ date -u +'%Y-%m-%d %H:%M:%S UTC'; }
echo "[$(ts)] ▶️ accuracy tick" | tee -a "$LOG"
python3 "$ROOT/tools/signal_accuracy.py" >> "$LOG" 2>&1 || true
echo "[$(ts)] ✅ tick done" | tee -a "$LOG"
