#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
TOOLS="$HOME/BotA/tools"

echo "=== metrics_signals ==="
python3 "$TOOLS/metrics_signals.py"

echo
echo "=== connectivity_audit ==="
python3 "$TOOLS/connectivity_audit.py"

echo
echo "=== bota_status ==="
"$TOOLS/bota_status.sh"
