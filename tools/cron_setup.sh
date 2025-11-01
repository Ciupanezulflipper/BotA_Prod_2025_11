#!/bin/bash
# cron_setup.sh — Termux-safe crontab installer for BotA

set -euo pipefail
ROOT="$HOME/BotA"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

# Use writable folder for temp cron file
CRONFILE="$ROOT/tmp_bota_cron.txt"
mkdir -p "$ROOT"

cat > "$CRONFILE" <<EOF
# BotA quiet schedules (UTC)
0  * * * * bash $ROOT/tools/heartbeat.sh      >> $LOGDIR/cron.heartbeat.log 2>&1
4  * * * * bash $ROOT/tools/autostatus.sh     >> $LOGDIR/cron.autostatus.log 2>&1
59 23 * * * bash $ROOT/tools/daily_summary.sh >> $LOGDIR/cron.daily.log 2>&1
55 * * * * bash $ROOT/tools/logrotate.sh      >> $LOGDIR/cron.rotate.log 2>&1
EOF

crontab "$CRONFILE"
echo "✅ Installed crontab:"
crontab -l
