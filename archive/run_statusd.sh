#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Load env (API keys + Telegram)
if [ -f "$HOME/.env" ]; then
  # export all non-comment vars
  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "$HOME/.env" | sed 's/\r$//')
  set +a
fi

# Default 15m if not in env
export STATUS_HEARTBEAT_SEC="${STATUS_HEARTBEAT_SEC:-900}"

mkdir -p "$HOME/bot-a/logs"
LOG="$HOME/bot-a/logs/statusd.log"

# Start daemon
python3 "$HOME/bot-a/tools/status_cmd.py" --daemon >>"$LOG" 2>&1 &
echo "statusd started (PID $!)"
