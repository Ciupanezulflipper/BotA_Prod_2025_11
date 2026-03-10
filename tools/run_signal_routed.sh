#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Ensure env and helpers
if [ -f "$HOME/BotA/.env" ]; then
  set -a; . "$HOME/BotA/.env"; set +a
fi

BOT_STATE="$HOME/BotA/tools/bot_state.sh"
PAIR="${1:-UNKNOWN}"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

if bash "$BOT_STATE" is_paused; then
  # Emit a single-line, greppable marker without touching any data providers.
  echo "[skip] $(ts) paused=true pair=${PAIR} reason=bot_state"
  exit 0
fi

# Not paused: forward to the real strategy tick
exec "$HOME/BotA/tools/run_signal_once.py" "$@"
