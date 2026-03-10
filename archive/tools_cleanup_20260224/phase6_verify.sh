#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

echo "=== Phase 6: Supervisor check ==="
"$TOOLS/supervise_bot.sh"

echo
echo "=== Phase 6: Daily report (DRY) ==="
DRY=1 python3 "$TOOLS/daily_report.py"

echo
echo "=== Phase 6: Daily report (push) ==="
python3 "$TOOLS/daily_report.py"

echo
echo "=== Phase 6: PASSED (smoke) ==="
