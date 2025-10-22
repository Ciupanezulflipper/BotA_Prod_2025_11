#!/bin/bash
# tools/heartbeat.sh
# Periodically send health ping to Telegram.

APP="$HOME/bot-a"
LOGDIR="$HOME/.bot-a/logs"
RUNFILE="$HOME/.bot-a/run/heartbeat.pid"

INTERVAL=1800   # 30 minutes (in seconds)

echo $$ > "$RUNFILE"

while true; do
    echo "[heartbeat] running health ping at $(date -u)"
    PYTHONPATH="$APP" python "$APP/tools/health_ping.py"
    sleep $INTERVAL
done
