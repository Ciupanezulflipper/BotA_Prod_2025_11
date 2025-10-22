#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PAIR="${1:-EURUSD}"

PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
export HOME PREFIX PATH="$PREFIX/bin:/system/bin" PYTHONPATH="$HOME" \
       LD_LIBRARY_PATH="$PREFIX/lib" LD_PRELOAD="$PREFIX/lib/libtermux-exec.so"

LOCK_DIR="$HOME/tmp"; mkdir -p "$LOCK_DIR"
LOCK_FILE="$LOCK_DIR/BotA.${PAIR}.lock"

# Open LOCK_FILE on fd 9 and try to take a non-blocking lock
(
  flock -n 9 || { echo "[LOCK] ${PAIR} already running, skipping."; exit 0; }
  cd "$HOME"
  set -a; [ -f "$HOME/.env.runtime" ] && . "$HOME/.env.runtime"; set +a
  echo "[RUN $(date -u +'%F %T') UTC] ${PAIR} starting"
  exec "$PREFIX/bin/python3" -m BotA.tools.final_runner --symbol "$PAIR" --send
) 9>"$LOCK_FILE"
