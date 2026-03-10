#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HB="$HOME/bot-a/data/last_heartbeat.txt"
LOG="$HOME/bot-a/logs/auto_restart.log"
CTRL_SH="$HOME/bot-a/tools/tg_control.sh"   # adjust if your controller entry differs
STALE_SECS="${1:-300}"  # default 5 minutes

now_utc="$(date -u +'%s')"
if [[ -f "$HB" ]]; then
  hb_str="$(tail -n 1 "$HB" || true)"
  hb_ts="$(date -u -d "${hb_str% UTC}" +'%s' 2>/dev/null || echo 0)"
else
  hb_ts=0
fi

age=$(( now_utc - hb_ts ))
if (( age > STALE_SECS )); then
  echo "[$(date -u +'%F %T UTC')] HEARTBEAT stale (${age}s) -> restarting controller" | tee -a "$LOG"
  pkill -f tg_control.py || true
  sleep 1
  nohup "$CTRL_SH" >/dev/null 2>&1 &
else
  echo "[$(date -u +'%F %T UTC')] HEARTBEAT OK (${age}s)" >> "$LOG"
fi
