#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
PAIR="${1:-EURUSD}"

PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
export HOME PREFIX PATH="$PREFIX/bin:/system/bin" PYTHONPATH="$HOME" \
       LD_LIBRARY_PATH="$PREFIX/lib" LD_PRELOAD="$PREFIX/lib/libtermux-exec.so" \
       TG_SEND_BUDGET="${TG_SEND_BUDGET:-1}"

cd "$HOME"
set -a; [ -f "$HOME/.env.runtime" ] && . "$HOME/.env.runtime"; set +a
mkdir -p "$HOME/BotA/tmp"

LOCK="$HOME/BotA/tmp/${PAIR}.lock"
echo "[RUN $(date -u +'%F %T') UTC] $PAIR starting" | tee -a "$HOME/BotA/run.log"

if command -v flock >/dev/null 2>&1; then
  # Proper flock usage: no -c; give it the program and args directly
  if ! flock -n "$LOCK" "$PREFIX/bin/python3" -m BotA.tools.final_runner --symbol "$PAIR" --send; then
    echo "[LOCK] $PAIR already running, skipping." | tee -a "$HOME/BotA/run.log"
    exit 0
  fi
else
  # Fallback lock via mkdir
  if mkdir "$LOCK".d 2>/dev/null; then
    trap 'rmdir "$LOCK".d' EXIT
    "$PREFIX/bin/python3" -m BotA.tools.final_runner --symbol "$PAIR" --send
  else
    echo "[LOCK] $PAIR already running (mkdir), skipping." | tee -a "$HOME/BotA/run.log"
  fi
fi
