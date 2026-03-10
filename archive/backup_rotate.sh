#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TS=$(date -u +%Y%m%d)
ROOT="$HOME/bot-a"
BK="$ROOT/backups"
LOGS="$ROOT/logs"

mkdir -p "$BK"

# what to backup (add/remove paths as you like)
INCLUDE=(
  "$ROOT/.env"
  "$LOGS"
  "$ROOT/state"
  "$ROOT/tools"
  "$ROOT/signals"
  "$ROOT/indicators"
  "$ROOT/cronfile.txt"
)

TAR="$BK/bot-a-$TS.tgz"
tar -czf "$TAR" "${INCLUDE[@]}" 2>/dev/null || true
echo "Backup written: $TAR"

# prune backups older than 14 days
find "$BK" -type f -name 'bot-a-*.tgz' -mtime +14 -print -delete | sed 's/^/Pruned: /' || true
