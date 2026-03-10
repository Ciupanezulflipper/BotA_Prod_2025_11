#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
COOLDOWN_MIN="${HEARTBEAT_COOLDOWN_MIN:-50}"
STAMP="$HOME/.cache/bota_heartbeat.ts"
REASON="${1:-hourly}"

mkdir -p "$(dirname "$STAMP")"

# Always allow immediate heartbeats on these reasons
if [[ "$REASON" =~ ^(startup|restart|restart-scanner|restart-tg|test)$ ]]; then
  python3 "$HOME/bot-a/tools/status_cmd.py" --heartbeat "reason=$REASON" && date +%s >"$STAMP"
  exit 0
fi

now=$(date +%s); last=0
[[ -f "$STAMP" ]] && last=$(cat "$STAMP" 2>/dev/null || echo 0)

if (( now - last < COOLDOWN_MIN*60 )); then
  echo "[HB] suppressed (cooldown ${COOLDOWN_MIN}m)."
  exit 0
fi

python3 "$HOME/bot-a/tools/status_cmd.py" --heartbeat "reason=$REASON" && date +%s >"$STAMP"
