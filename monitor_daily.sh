#!/usr/bin/env bash
set -eu
LOGDIR="$HOME/TomaMobileForexBot/logs"
mkdir -p "$LOGDIR"

STAMP="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
OUT="$LOGDIR/monitor_$(date -u +'%Y-%m-%d').log"

{
  echo "===== Monitor snapshot @ $STAMP (UTC) ====="
  "$HOME/TomaMobileForexBot/monitor_bot.sh"
  echo
} >> "$OUT" 2>&1
