#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BOT="$HOME/bot-a"
TOOLS="$BOT/tools"
LOG="$BOT/logs/autopilot.log"
mkdir -p "$BOT/logs"

# Consistent TZ from device (Termux props) with UTC fallback
export TZ="${TZ:-$(getprop persist.sys.timezone || getprop persist.sys.locale.timezone || "UTC")}"

cd "$TOOLS"

# --- Single-run lock (prevents overlap) ---
LOCK="$BOT/data/runner_autopilot.lock"
AGE="$( [ -f "$LOCK" ] && echo $(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) )) || echo 99999 )"
if [ -f "$LOCK" ] && [ "${AGE:-99999}" -lt 540 ]; then
  printf "[autopilot] skip: last run %s sec ago (%s) TZ=%s\n" "$AGE" "$(date -Is)" "$TZ" >>"$LOG"
  exit 0
fi
date +%s > "$LOCK" || true

# --- One-shot runner babysit (very quiet) ---
python3 "$TOOLS/runner_confluence.py" --pair EURUSD --tf M15 --force --dry-run=false >/dev/null 2>&1 || true

# --- Hourly status card (only at mm==00) ---
if [ "$(date +%M)" = "00" ]; then
  python3 "$TOOLS/status_card.py" --send >/dev/null 2>&1 || true
fi

printf "[autopilot] ok %s TZ=%s\n" "$(date -Is)" "$TZ" >>"$LOG"
exit 0
