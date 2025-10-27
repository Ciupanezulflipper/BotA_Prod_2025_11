#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
STATE="$ROOT/state"
LOG="$ROOT/control.log"

mkdir -p "$STATE"

# 1) Ensure the Python controller exists
if [ ! -f "$TOOLS/tele_control.py" ]; then
  echo "[tele_control] Missing tele_control.py — please install it first." >&2
  exit 1
fi

# 2) Ensure exactly one instance is running
if pgrep -f "python3 .*tele_control.py" >/dev/null 2>&1; then
  echo "[tele_control] Controller already running."
  exit 0
fi

# 3) Boot the Telegram controller (long-polling)
echo "[tele_control] Starting controller…" | tee -a "$LOG"
nohup python3 "$TOOLS/tele_control.py" >> "$LOG" 2>&1 & disown
echo "[tele_control] Started (log: $LOG)"
