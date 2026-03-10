#!/data/data/com.termux/files/usr/bin/bash
# Wrapper for Telegram control

BOT_DIR=$HOME/bot-a
TOOLS_DIR=$BOT_DIR/tools
LOGS_DIR=$BOT_DIR/logs
mkdir -p "$LOGS_DIR"

LOG_FILE=$LOGS_DIR/tg_control.log
PID_FILE=$LOGS_DIR/tg_control.pid

# Prevent duplicate runs
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
  echo "tg_control already running (PID=$(cat $PID_FILE))"
  exit 0
fi

echo $$ > "$PID_FILE"
echo "[$(date -u)] tg_control started" >> "$LOG_FILE"

exec python3 $TOOLS_DIR/tg_control.py >> "$LOG_FILE" 2>&1
