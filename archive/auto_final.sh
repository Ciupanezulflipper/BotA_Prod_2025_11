#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/bot-a"

# Export .env to shell for any child processes
set -a
[ -f "$BASE/.env" ] && . "$BASE/.env"
set +a

# >>> your existing cadence/watchlist loop code goes below <<<
# (keep your current script body unchanged)
