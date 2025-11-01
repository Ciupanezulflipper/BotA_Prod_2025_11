#!/usr/bin/env bash
set -euo pipefail
ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOG="${ROOT}/logs/cron.accuracy.log"
mkdir -p "${ROOT}/logs"

TMP="$(mktemp)"
# keep everything except prior installs of these two tools
crontab -l 2>/dev/null | grep -vE 'signal_accuracy\.py|daily_accuracy_summary\.sh' > "$TMP" || true

# Accuracy evaluator: every 15 minutes
printf "*/15 * * * * BOTA_ROOT=%s python3 %s/tools/signal_accuracy.py >> %s 2>&1\n" \
  "$ROOT" "$ROOT" "$LOG" >> "$TMP"

# Daily summary: 00:05 UTC
printf "5 0 * * * BOTA_ROOT=%s bash %s/tools/daily_accuracy_summary.sh >> %s 2>&1\n" \
  "$ROOT" "$ROOT" "$ROOT/logs/daily_summary.log" >> "$TMP"

crontab "$TMP"
rm -f "$TMP"

echo "✅ Installed:"
echo "  • */15 * * * * python3 tools/signal_accuracy.py"
echo "  • 5 0 * * *   bash tools/daily_accuracy_summary.sh"
echo "Logs:"
echo "  • $LOG"
echo "  • $ROOT/logs/daily_summary.log"
