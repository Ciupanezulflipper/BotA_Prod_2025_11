#!/bin/bash
# cron_signals.sh — install/refresh the */5 cron for signal_watcher_pro.sh
set -euo pipefail
ROOT="$HOME/BotA"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"
TMP="$(mktemp)"
# Keep other entries; replace our own line idempotently
crontab -l 2>/dev/null | grep -v 'signal_watcher_pro.sh' > "$TMP" || true
printf "*/5 * * * * bash %s/tools/signal_watcher_pro.sh >> %s/cron.signals.log 2>&1\n" "$ROOT" "$LOGDIR" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"
echo "✅ Installed cron: */5 * * * * signal_watcher_pro.sh"
