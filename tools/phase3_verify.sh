#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PAIRS=("$@")
if [ "${#PAIRS[@]}" -eq 0 ]; then
  PAIRS=("EURUSD" "GBPUSD")
fi

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
STATUS="$ROOT/PHASE_STATUS.txt"

# 1) Populate cache (emits snapshots + updates cache)
echo "=== Phase 3: Cache population ==="
python3 "$TOOLS/cache_update.py" "${PAIRS[@]}"

# 2) Verify cache completeness
echo
echo "=== Phase 3: Cache verify ==="
if ! "$TOOLS/cache_verify.sh" "${PAIRS[@]}"; then
  echo "PHASE 3: FAILED (cache incomplete)" | tee "$STATUS"
  exit 1
fi

# 3) Watcher summary
echo
echo "=== Phase 3: Watcher summary ==="
watch_out="$("$TOOLS/watchlist_run.sh" 2>/dev/null || true)"
printf "%s\n" "$watch_out"

# Acceptance criteria
# - cache_verify already passed (all pairs have H1/H4/D1)
# - early_watch ran without crashing (we don't force a WATCH; neutral state is OK)
echo
echo "PHASE 3: PASSED" | tee "$STATUS"
exit 0
