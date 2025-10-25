#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

echo "=== Phase 10: Logrotate (DRY) ==="
DRY=1 MAX_KB=1 KEEP=3 "$TOOLS/logrotate.sh"

echo
echo "=== Phase 10: Supervisor (start/age) ==="
RESTART_AGE_SEC=1 HEALTH_ON_START=1 "$TOOLS/supervise_bot.sh"

echo
echo "=== Phase 10: Health ping (DRY) ==="
DRY=1 python3 "$TOOLS/health_ping.py"

echo
echo "=== Phase 10: PASSED (smoke) ==="
