#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${REPO:-$HOME/BotA}"
LOG_DIR="$REPO/logs"
LOG_FILE="$LOG_DIR/cron.signals.log"

mkdir -p "$LOG_DIR"

ts() { date -Iseconds; }

cmd="${1:-rotate}"
case "$cmd" in
  rotate)
    if [ -f "$LOG_FILE" ]; then
      dst="${LOG_FILE}.$(ts)"
      mv -f "$LOG_FILE" "$dst"
      echo "[logclean] rotated $LOG_FILE -> $dst"
    else
      echo "[logclean] no existing $LOG_FILE to rotate"
    fi
    : > "$LOG_FILE"
    echo "[logclean] created fresh $LOG_FILE"
    ;;
  truncate)
    : > "$LOG_FILE"
    echo "[logclean] truncated $LOG_FILE"
    ;;
  *)
    echo "usage: $0 {rotate|truncate}" >&2
    exit 1
    ;;
esac
