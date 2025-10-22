#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/bot-a"
PIDFILE="$BASE/run/auto_final.pid"
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE")
  kill "$PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "auto_final stopped (pid was $PID)."
else
  echo "no pidfile found."
fi
