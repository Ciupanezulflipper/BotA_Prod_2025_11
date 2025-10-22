#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HOME_DIR="$HOME/bot-a"
LOGD="$HOME_DIR/logs"
LOG="$LOGD/auto_conf.log"
TOOLS="$HOME_DIR/tools"

mkdir -p "$LOGD"
touch "$LOG"

# Start tail; for each "card start", let Python grab the latest block
tail -n 0 -F "$LOG" | \
  awk '/---- card start ----/{print; fflush(); system("'"$TOOLS"'/journal_signals.py --from-log)}' \
  >/dev/null 2>&1
