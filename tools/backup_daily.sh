#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BOT="$HOME/bot-a"
BKDIR="$BOT/backups"
mkdir -p "$BKDIR"

STAMP=$(date +%Y%m%d-%H%M)
OUT="$BKDIR/bot-a-$STAMP.tar.gz"

tar -czf "$OUT" \
  -C "$HOME" \
  bot-a/tools \
  bot-a/data \
  bot-a/logs \
  bot-a/.env || true

# keep last 7 backups
ls -1t "$BKDIR"/bot-a-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f

# prune very old logs (already rotating, but double-safe)
find "$BOT/logs" -type f -name "*.log" -mtime +14 -delete 2>/dev/null || true
