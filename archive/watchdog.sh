#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE_DIR="${BASE_DIR:-$HOME/BotA}"
LOGS="${LOG_DIR:-$BASE_DIR/logs}"
TOOLS="${TOOLS:-$BASE_DIR/tools}"
STATE_DIR="${STATE_DIR:-$BASE_DIR/state}"
mkdir -p "$LOGS" "$STATE_DIR"

ts() { date -u +%FT%TZ; }

# Count loops
mapfile -t pids < <(ps -ef | awk '/BotA\/tools\/run_loop\.sh/ && !/awk/ && !/grep/ {print $2}')
count="${#pids[@]}"

if [[ "$count" -eq 0 ]]; then
  echo "[INFO] $(ts) watchdog: no run_loop found, starting via loop_guard" >> "$LOGS/watchdog.log"
  bash "$TOOLS/loop_guard.sh" daemon >> "$LOGS/watchdog.log" 2>&1 || true
elif [[ "$count" -gt 1 ]]; then
  echo "[warn] $(ts) watchdog: multiple run_loop found (${count}), pruning extras" >> "$LOGS/watchdog.log"
  # Keep the oldest (first in ps -ef order), kill the rest
  keep="${pids[0]}"
  for pid in "${pids[@]:1}"; do
    kill "$pid" 2>/dev/null || true
  done
  echo "$keep" > "$STATE_DIR/loop.pid"
fi

# Optional: restart if loop.log stale (>10 minutes)
LOGF="$LOGS/loop.log"
if [[ -f "$LOGF" ]]; then
  last_mod=$(date -u -r "$LOGF" +%s)
  now=$(date -u +%s)
  if (( now - last_mod > 600 )); then
    echo "[warn] $(ts) watchdog: loop.log stale (>10m). Restarting daemon." >> "$LOGS/watchdog.log"
    pkill -f "BotA/tools/run_loop\.sh" 2>/dev/null || true
    sleep 1
    bash "$TOOLS/loop_guard.sh" daemon >> "$LOGS/watchdog.log" 2>&1 || true
  fi
fi
