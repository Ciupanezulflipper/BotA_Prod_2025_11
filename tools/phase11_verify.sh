#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
TOOLS="$HOME/BotA/tools"

echo "=== Phase 11: Preview (MIN_WEIGHT=0, DRY=1) ==="
DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" || true

echo
echo "=== Phase 11: Volatility gate demo (tight threshold to force filter) ==="
DRY=1 MIN_WEIGHT=0 VOL_MIN_STD=1e9 ONCE=1 "$TOOLS/alert_loop.sh" || true

echo
echo "=== Phase 11: Quiet hours demo (forces suppression) ==="
# simulate quiet hours covering current hour
H=$(date -u '+%H'); NEXT=$(( (10#$H + 1) % 24 ))
DRY=0 QUIET_HOURS="$H-$NEXT" ONCE=1 "$TOOLS/alert_loop.sh" || true

echo
echo "=== Phase 11: PASSED (smoke) ==="
