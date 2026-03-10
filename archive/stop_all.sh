#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/stop_all.sh
# DESC: Cleanly stop telecontroller + watcher (SIGTERM → wait → SIGKILL)
set -euo pipefail

stop_by_pattern() {
  local pattern="$1"
  local name="$2"

  local pids
  pids="$(pgrep -f "$pattern" || true)"
  if [ -z "$pids" ]; then
    echo "[stop_all] no $name running"
    return 0
  fi

  echo "[stop_all] stopping $name (SIGTERM): $pids"
  kill -15 $pids 2>/dev/null || true

  # wait up to 10s for graceful exit
  for i in {1..10}; do
    sleep 1
    if ! pgrep -f "$pattern" >/dev/null; then
      echo "[stop_all] $name stopped cleanly after ${i}s"
      break
    fi
  done

  # force if still alive
  if pgrep -f "$pattern" >/dev/null; then
    echo "[stop_all] $name still running → forcing SIGKILL"
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}

# Stop order: watcher → telecontroller → any legacy tg controllers
stop_by_pattern "watch_wrap_market\.sh|wrap_watch_market\.sh|signal_watcher_pro\.sh" "watcher"
stop_by_pattern "tools/telecontroller\.py" "telecontroller"
stop_by_pattern "tools/(tele_control\.py|tg_control\.py|tg_menu\.py|telegram_menu\.py)" "legacy tg controllers"

echo "[stop_all] final status:"
pgrep -af -f "watch_wrap_market\.sh|wrap_watch_market\.sh|signal_watcher_pro\.sh|tools/telecontroller\.py|tools/(tele_control\.py|tg_control\.py|tg_menu\.py|telegram_menu\.py)" \
  || echo "(none running)"
