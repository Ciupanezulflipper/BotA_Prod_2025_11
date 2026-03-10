#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BACK_DIR="$HOME/bot-a/backups"
LOG_DIR="$HOME/bot-a/logs"
STAMP="$(date -u +%Y%m%d_%H%MZ)"

mkdir -p "$BACK_DIR"

# 1) tar.gz logs
tar -czf "$BACK_DIR/logs_$STAMP.tgz" -C "$LOG_DIR" .

# 2) optional: save a redacted env snapshot (no tokens)
if [ -f "$HOME/.env" ]; then
  awk '
    BEGIN{IGNORECASE=1}
    /TELEGRAM_BOT_TOKEN|API_KEY|TOKEN|SECRET/ {print $1"=REDACTED"; next}
    {print}
  ' "$HOME/.env" > "$BACK_DIR/env_$STAMP.redacted"
fi

# keep only last 14 backups
ls -1t "$BACK_DIR"/logs_*.tgz 2>/dev/null | sed -n '15,$p' | xargs -r rm -f
ls -1t "$BACK_DIR"/env_*.redacted 2>/dev/null | sed -n '15,$p' | xargs -r rm -f

echo "Backup done -> $BACK_DIR (stamp: $STAMP)"
