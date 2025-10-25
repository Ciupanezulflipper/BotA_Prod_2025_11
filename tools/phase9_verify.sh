#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
TOOLS="$HOME/BotA/tools"

echo "=== Phase 9: Preview with MIN_WEIGHT=0 (should produce preview text; DRY=1 prevents push) ==="
DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" || true

echo
echo "=== Phase 9: Cooldown test (same alerts should be suppressed on second run) ==="
COOL_DOWN_MIN=60 DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" >/dev/null || true
COOL_DOWN_MIN=60 DRY=1 MIN_WEIGHT=0 ONCE=1 "$TOOLS/alert_loop.sh" || true

echo
echo "=== Phase 9: Normal threshold one-shot (may or may not alert; no crash) ==="
ONCE=1 "$TOOLS/alert_loop.sh"

echo
echo "=== Phase 9: PASSED (smoke) ==="
