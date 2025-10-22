#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
export HOME PREFIX PATH="$PREFIX/bin:/system/bin" PYTHONPATH="$HOME" \
       LD_LIBRARY_PATH="$PREFIX/lib" LD_PRELOAD="$PREFIX/lib/libtermux-exec.so"
cd "$HOME"
set -a; [ -f "$HOME/.env.runtime" ] && . "$HOME/.env.runtime"; set +a
exec "$PREFIX/bin/python3" -m BotA.tools.final_runner --symbol "${1:-EURUSD}" --send
