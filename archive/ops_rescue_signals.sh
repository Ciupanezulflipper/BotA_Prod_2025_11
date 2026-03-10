#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/ops_rescue_signals.sh
# PURPOSE: Start/stop/status wrapper for watcher with PID/Log handling
# USAGE: ./ops_rescue_signals.sh [--start-watch|--stop-watch|--status|--restart]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PID_FILE="$ROOT_DIR/cache/watcher.pid"
LOG_FILE="$ROOT_DIR/logs/watcher_nohup.log"
WATCHER="$ROOT_DIR/tools/signal_watcher_pro.sh"
CONFIG="$ROOT_DIR/config/strategy.env"
ENVFILE="$ROOT_DIR/.env"

log_i(){ echo "[OPS $(date -u +%Y-%m-%dT%H:%M:%SZ)] INFO: $*"; }
log_e(){ echo "[OPS $(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2; }

is_running(){
  if [ -f "$PID_FILE" ]; then
    local p; p="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "${p:-}" ] && ps -p "$p" >/dev/null 2>&1 && { echo "$p"; return 0; }
  fi
  return 1
}

start(){
  mkdir -p "$ROOT_DIR/logs" "$ROOT_DIR/cache"
  if p="$(is_running)"; then
    log_i "Watcher already running (PID $p)"
    exit 0
  fi
  [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
  # light log rotation (1 gen)
  [ -f "$LOG_FILE" ] && mv "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null || true

  log_i "Starting watcher…"
  # Inherit env to child nohup (preload config/.env)
  nohup bash -c "set -a; source '$CONFIG'; [ -f '$ENVFILE' ] && source '$ENVFILE'; set +a; exec '$WATCHER'" \
    >>"$LOG_FILE" 2>&1 &

  echo $! > "$PID_FILE"
  sleep 1
  if ! p="$(is_running)"; then
    log_e "watcher failed to start. Tail:"
    tail -n 20 "$LOG_FILE" || true
    exit 1
  fi
  log_i "Watcher RUNNING (PID $(cat "$PID_FILE"))"
}

stop(){
  if ! p="$(is_running)"; then
    log_i "Watcher not running. Cleaning stale PID if any."
    rm -f "$PID_FILE" || true
    exit 0
  fi
  log_i "Stopping watcher PID $p"
  kill "$p" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    sleep 1
    ps -p "$p" >/dev/null 2>&1 || { rm -f "$PID_FILE"; log_i "Stopped."; return 0; }
  done
  log_i "Force killing PID $p"
  kill -9 "$p" 2>/dev/null || true
  rm -f "$PID_FILE" || true
  log_i "Stopped."
}

status(){
  if p="$(is_running)"; then
    log_i "RUNNING (PID $p)"
    log_i "LOG TAIL: $(tail -n 1 "$LOG_FILE" 2>/dev/null || echo "(no log)")"
  else
    log_i "STOPPED"
    [ -f "$PID_FILE" ] && log_i "NOTE: Stale PID file present"
  fi
}

case "${1:-}" in
  --start-watch) start ;;
  --stop-watch)  stop ;;
  --restart)     stop; start ;;
  --status|*)    status ;;
esac
