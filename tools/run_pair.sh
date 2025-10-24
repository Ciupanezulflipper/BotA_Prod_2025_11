#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
PAIR="${1:-EURUSD}"
LOG="$HOME/BotA/run.log"
echo "[RUN $(date -u '+%Y-%m-%d %H:%M:%S UTC')] $PAIR starting" | tee -a "$LOG"
python3 "$HOME/BotA/tools/emit_snapshot.py" "$PAIR" | tee -a "$LOG"
