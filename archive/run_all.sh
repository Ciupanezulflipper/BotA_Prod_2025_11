#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/run_all.sh
# DESC: Start telecontroller + watcher safely (idempotent). Also supports check/restart.
set -euo pipefail
cd "$HOME/BotA"
mkdir -p logs cache

# Load env if present (for watcher scripts)
if [ -f config/strategy.env ]; then
  # shellcheck disable=SC1091
  . config/strategy.env
  export TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
  export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
fi

already() { pgrep -f "$1" >/dev/null 2>&1; }

start_controller() {
  if already "tools/telecontroller_curl.py"; then
    echo "[run_all] telecontroller already running"
  else
    echo "[run_all] starting telecontroller…"
    nohup python3 tools/telecontroller_curl.py >> logs/telecontroller.log 2>&1 & disown || true
    sleep 1
    pgrep -af -f "tools/telecontroller_curl.py" >/dev/null || { echo "[run_all] ERROR: telecontroller failed to start"; exit 1; }
  fi
}

start_watcher() {
  if already "tools/watch_wrap_market\.sh"; then
    echo "[run_all] watcher wrapper already running"
  else
    echo "[run_all] starting watcher wrapper…"
    nohup bash tools/watch_wrap_market.sh >> logs/watcher_nohup.log 2>&1 & disown || true
    sleep 2
    pgrep -af -f "tools/watch_wrap_market\.sh" >/dev/null || { echo "[run_all] ERROR: watcher failed to start"; exit 1; }
  fi
}

case "${1:-start}" in
  start)    start_controller; start_watcher ;;
  controller) start_controller ;;
  watcher)   start_watcher ;;
  restart)  ./tools/stop_all.sh || true; sleep 2; start_controller; start_watcher ;;
  check)    ./tools/status_all.sh; exit 0 ;;
  *) echo "Usage: $0 [start|controller|watcher|restart|check]"; exit 2 ;;
esac

./tools/status_all.sh || true
