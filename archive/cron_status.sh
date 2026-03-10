#!/usr/bin/env bash
set -euo pipefail

BASE="$HOME/bot-a"
TOOLS="$BASE/tools"
LOGS="$BASE/logs"
TMP="$BASE/tmp"

mkdir -p "$LOGS" "$TMP"

# load Telegram env (TOKEN & CHAT_ID)
set -a
. "$BASE/config/tele.env"
set +a

ts() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

{
  echo "[$(ts)] status job start"
  python3 "$TOOLS/status_card.py" --send || echo "[$(ts)] WARN: status_card failed"
  echo "[$(ts)] status job end"
} >> "$LOGS/status.log" 2>&1
