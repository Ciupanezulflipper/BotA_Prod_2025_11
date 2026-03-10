#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"

# 1) Dry-run with zero threshold to preview formatting (won't push if DRY=1)
echo "=== Phase 5: Dry preview (MIN_WEIGHT=0, DRY=1) ==="
DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" || true

# 2) Normal one-shot at default threshold (2). Should not crash; may or may not alert.
echo
echo "=== Phase 5: Normal one-shot (MIN_WEIGHT=2) ==="
ONCE=1 "$TOOLS/alert_loop.sh"

echo
echo "=== Phase 5: PASSED (smoke) ==="
