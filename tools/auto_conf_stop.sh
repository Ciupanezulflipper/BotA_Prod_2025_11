#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
PIDF="$HOME/bot-a/logs/auto_conf.pid"

if [[ -f "$PIDF" ]] && ps -p "$(cat "$PIDF")" >/dev/null 2>&1; then
  kill "$(cat "$PIDF")" || true
  sleep 1
fi
rm -f "$PIDF"
echo "auto_conf: stopped"
