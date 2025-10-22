#!/data/data/com.termux/files/usr/bin/bash
set -e

LOG="$HOME/bot-a/bot_run.log"
SIG="$HOME/bot-a/signals.csv"
KEEP=7

# Ensure files exist
touch "$LOG"
touch "$SIG"

# Rotate bot_run.log -> bot_run.log.1..KEEP (keep last 7)
for ((i=$KEEP; i>=2; i--)); do
  if [ -f "$LOG.$((i-1))" ]; then
    mv -f "$LOG.$((i-1))" "$LOG.$i"
  fi
done
# Move current -> .1 and truncate current
cp -f "$LOG" "$LOG.1" 2>/dev/null || true
: > "$LOG"

# Optional: trim signals.csv to last 2000 lines (prevent bloat)
TMP="$(mktemp)"
tail -n 2000 "$SIG" > "$TMP" 2>/dev/null || true
mv -f "$TMP" "$SIG"

echo "[rotate_logs] done: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
