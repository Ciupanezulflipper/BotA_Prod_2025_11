#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
log() { printf "%s %s\n" "$(date -Iseconds)" "$*"; }

# Resolve repo root
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# 0) Ensure dirs
mkdir -p logs cache

# 1) Show effective config
log "== 1) Config snapshot =="
set -a; source config/strategy.env; set +a
echo "PAIRS=${PAIRS}"
echo "TIMEFRAMES=${TIMEFRAMES}"
echo "TELEGRAM_ENABLED=${TELEGRAM_ENABLED:-0}"
echo "TELEGRAM_DASHBOARD=${TELEGRAM_DASHBOARD:-0}"
echo "TELEGRAM_MIN_SCORE=${TELEGRAM_MIN_SCORE:-}"
echo "ALERTS_CSV=${ALERTS_CSV}"

# 2) Telegram ping (required)
log "== 2) Telegram ping =="
bash tools/telegram_test.sh || { echo "❌ Telegram test failed"; exit 2; }

# 3) Single scan (does not background)
log "== 3) Single scan (all PAIRS×TF) =="
bash tools/signal_watcher_pro.sh --once 2>&1 | tail -n 60 || true

# 4) Alerts tail (last 10)
log "== 4) Alerts tail =="
if [[ -f "$ALERTS_CSV" ]]; then
  tail -n 10 "$ALERTS_CSV" || true
else
  echo "no alerts yet"
fi

# 5) Hourly dashboard (text summary + optional Telegram)
log "== 5) Hourly dashboard preview =="
bash tools/hourly_dashboard.sh || true
tail -n 1 logs/dashboard_hourly.txt || true

# 6) Heartbeat check (emulated)
date +%s > cache/watcher.heartbeat
sleep 1
age=$(( $(date +%s) - $(cat cache/watcher.heartbeat) ))
log "== 6) Heartbeat age: ${age}s =="

log "== Smoke suite complete =="
