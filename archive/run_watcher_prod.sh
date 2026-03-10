#!/data/data/com.termux/files/usr/bin/bash
# BotA production runner (wrapper)
# Why this exists:
# - Ensures PAIRS/TIMEFRAMES/SLEEP_SECONDS are set in the environment BEFORE watcher loads .env,
#   because watcher uses a no-override .env loader.
# - Lets you change scope safely without editing tools/signal_watcher_pro.sh.

set -euo pipefail
cd /data/data/com.termux/files/home/BotA || exit 1

# ===== Production scope (edit here when you want to expand) =====
: "${PAIRS:=GBPUSD}"
: "${TIMEFRAMES:=M15}"
: "${SLEEP_SECONDS:=300}"   # 300s = 5 minutes
# ===============================================================

export PAIRS TIMEFRAMES SLEEP_SECONDS

# Default mode: loop forever (watcher handles locking)
# Use: --once for one scan
exec bash tools/signal_watcher_pro.sh "${@}"
