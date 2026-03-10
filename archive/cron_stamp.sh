#!/data/data/com.termux/files/usr/bin/bash
# Usage: cron_stamp.sh <name> <exit_code>
set -euo pipefail
NAME="${1:-unknown}"
CODE="${2:-0}"
STAMP_DIR="$HOME/bot-a/logs/stamps"
mkdir -p "$STAMP_DIR"
printf '%s UTC | exit=%s\n' "$(date -u +'%Y-%m-%d %H:%M:%S')" "$CODE" > "$STAMP_DIR/${NAME}.txt"
