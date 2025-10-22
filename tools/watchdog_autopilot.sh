#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BOT="$HOME/bot-a"
TOOLS="$BOT/tools"
LOGDIR="$BOT/logs"
mkdir -p "$LOGDIR"

# Keep TZ consistent with device (falls back to UTC)
export TZ="${TZ:-$(getprop persist.sys.timezone || getprop persist.sys.locale.timezone || "UTC")}"

ALERT() {
  python3 "$TOOLS/status_cmd.py" --alert "$1" || true
}

# 1) Autopilot log freshness
AUTOLOG="$LOGDIR/autopilot.log"
if [ -f "$AUTOLOG" ]; then
  now=$(date +%s)
  mtime=$(stat -c %Y "$AUTOLOG" 2>/dev/null || echo 0)
  age=$((now - mtime))
  if [ "$age" -gt 900 ]; then   # >15 min
    ALERT "⚠️ Autopilot silent for $((age/60)) min (check cron or Termux)."
  fi
else
  ALERT "⚠️ Autopilot log missing at $AUTOLOG"
fi

# 2) Runner lock freshness
LOCK="/data/data/com.termux/files/usr/tmp/runner.lock"
if [ -f "$LOCK" ]; then
  now=$(date +%s)
  mtime=$(stat -c %Y "$LOCK" 2>/dev/null || echo 0)
  age=$((now - mtime))
  if [ "$age" -gt 1800 ]; then  # >30 min
    ALERT "🛑 Runner appears stalled: runner.lock age $((age/60)) min."
  fi
else
  ALERT "⚠️ runner.lock missing (runner may not have started)."
fi

exit 0
