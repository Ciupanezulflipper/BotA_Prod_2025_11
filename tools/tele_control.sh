#!/data/data/com.termux/files/usr/bin/bash
# Wrapper to run the Telegram controller (idempotent)
set -euo pipefail

# Ensure env is present (use tele_env.sh if you like)
: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN}"
: "${TELEGRAM_CHAT_ID:?Missing TELEGRAM_CHAT_ID}"

# Single instance guard
PIDFILE="$HOME/BotA/.state/tele_control.pid"
mkdir -p "$HOME/BotA/.state"
if [[ -f "$PIDFILE" ]] && ps -p "$(cat "$PIDFILE")" >/dev/null 2>&1; then
  echo "[tele_control] already running (pid $(cat "$PIDFILE"))"
  exit 0
fi

python3 "$HOME/BotA/tools/tele_control.py" &
echo $! > "$PIDFILE"
echo "[tele_control] started (pid $(cat "$PIDFILE"))"
