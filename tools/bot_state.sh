#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Load env if present (non-fatal)
if [ -f "$HOME/BotA/.env" ]; then
  set -a; . "$HOME/BotA/.env"; set +a
fi

STATE_DIR="${STATE_DIR:-$HOME/BotA/state}"
mkdir -p "$STATE_DIR"

PAUSE_FILE="$STATE_DIR/bot.paused"

cmd="${1:-status}"

is_paused() {
  [ -f "$PAUSE_FILE" ]
}

case "$cmd" in
  status)
    if is_paused; then
      echo "paused"
      exit 0
    else
      echo "running"
      exit 0
    fi
    ;;
  pause|off)
    # create marker
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PAUSE_FILE"
    echo "paused"
    exit 0
    ;;
  resume|on)
    rm -f "$PAUSE_FILE"
    echo "running"
    exit 0
    ;;
  is_paused)
    if is_paused; then
      exit 0
    else
      exit 1
    fi
    ;;
  *)
    echo "usage: $0 {status|pause|off|resume|on|is_paused}" >&2
    exit 2
    ;;
esac
