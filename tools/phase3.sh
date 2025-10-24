#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"

PAIRS=("$@")
if [ "${#PAIRS[@]}" -eq 0 ]; then
  PAIRS=("EURUSD" "GBPUSD")
fi

echo "=== Phase 3: Cache population ==="
python3 "$TOOLS/cache_update.py" "${PAIRS[@]}"

echo
echo "=== Phase 3: Cache verify ==="
"$TOOLS/cache_verify.sh" "${PAIRS[@]}"

echo
echo "=== Phase 3: Watcher summary ==="
"$TOOLS/watchlist_run.sh"

echo
echo "=== Phase 3: DONE ==="
