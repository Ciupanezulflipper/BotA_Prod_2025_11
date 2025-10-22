#!/usr/bin/env bash
# Bot A Read-Only Audit — no network calls, no sends, no strategy runs.
# Produces a comprehensive TXT report for AI review.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/bot-a}"
LOG_DIR="$PROJECT_ROOT/logs"
STATE_DIR="$PROJECT_ROOT/state"
REPORT_DIR="$PROJECT_ROOT/logs"
NOW_UTC="$(date -u +'%Y-%m-%d %H:%M:%S')"
STAMP="$(date -u +'%Y%m%d_%H%MZ')"
REPORT="$REPORT_DIR/audit_readonly_$STAMP.txt"
SNAPSHOT="$STATE_DIR/sha256_snapshot.txt"
SNAPSHOT_NEW="$STATE_DIR/sha256_snapshot.$STAMP.txt"
AUTOLOG="$LOG_DIR/auto_h1.log"
ENVFILE="$PROJECT_ROOT/.env.botA"

ONLINE="${ONLINE:-0}"  # set ONLINE=1 to allow optional online checks (disabled by default)

mkdir -p "$LOG_DIR" "$STATE_DIR"

section () {
  echo -e "\n===== $1 =====" >> "$REPORT"
}

mask_val () {
  # mask tokens/keys while keeping first/last chars
  local v="$1"
  [ -z "$v" ] && { echo "(missing)"; return; }
  local n=${#v}
  if [ $n -le 8 ]; then echo "***MASKED***"
  else
    echo "${v:0:6}***${v: -4}"
  fi
}

echo "Bot A Read-Only Audit started $NOW_UTC" > "$REPORT"
echo "REPORT: $REPORT" >> "$REPORT"

# 1) System & env basics (no network)
section "SYSTEM"
{
  echo "UTC now      : $NOW_UTC"
  echo "Hostname     : $(uname -n)"
  echo "Kernel       : $(uname -srmo 2>/dev/null || uname -a)"
  echo "Uptime       : $(uptime 2>/dev/null || echo 'n/a')"
  echo "Disk usage   :"
  df -h "$PROJECT_ROOT" 2>/dev/null || true
  echo
  echo "Python       : $(python3 -V 2>&1 || echo 'python3 missing')"
  echo "Pip packages :"
  pip list 2>/dev/null | grep -E '^(python-telegram-bot|urllib3|pandas|requests)\s' || echo "(could not list / none of interest)"
} >> "$REPORT"

# 2) Project layout & key files
section "PROJECT & FILES"
{
  echo "PROJECT_ROOT : $PROJECT_ROOT"
  echo "Key files    :"
  for f in \
    tools/auto_h1.sh \
    tools/start_botA.sh \
    tools/runner_confluence.py \
    tools/tg_send.py \
    data/ohlcv.py \
    .env.botA \
    .termux/boot/start_botA.sh
  do
    if [ -f "$PROJECT_ROOT/$f" ]; then
      echo " - $f  ($(stat -c '%y %s bytes' "$PROJECT_ROOT/$f" 2>/dev/null || stat "$PROJECT_ROOT/$f" || true))"
      head -n1 "$PROJECT_ROOT/$f" | sed 's/^/   first line: /' || true
    else
      echo " - $f  (missing)"
    fi
  done
} >> "$REPORT"

# 3) Environment (masked)
section "ENV (.env.botA — masked)"
{
  if [ -f "$ENVFILE" ]; then
    echo "Present: yes"
    # Print only key lines; mask sensitive values
    awk -F= '
      $1 ~ /^(BOT_TOKEN|TELEGRAM_BOT_TOKEN|CHAT_ID|TWELVEDATA_API_KEY|ENV_TAG)$/ {
        print $1"="$2
      }' "$ENVFILE" \
      | while IFS='=' read -r k v; do
          if [[ "$k" =~ BOT_TOKEN|TELEGRAM_BOT_TOKEN|TWELVEDATA_API_KEY ]]; then
            mv="$(echo "$v" | tr -d '"'"'\r\n'"'"')"
            printf "%-20s = %s\n" "$k" "$(echo "$mv" | awk '{ if(length($0)<=8){print "***MASKED***"}else{print substr($0,1,6)"***"substr($0,length($0)-3,4)} }')"
          else
            printf "%-20s = %s\n" "$k" "$(echo "$v" | tr -d '\r\n')"
          fi
        done
  else
    echo "Present: no"
  fi
} >> "$REPORT"

# 4) tmux/session health (no changes)
section "TMUX SESSIONS"
{
  if command -v tmux >/dev/null 2>&1; then
    tmux ls 2>/dev/null || echo "(no tmux server)"
    echo
    tmux list-panes -a -F '#{session_name} dead=#{pane_dead} cmd=#{pane_current_command} path=#{pane_current_path}' 2>/dev/null || true
  else
    echo "tmux not installed"
  fi
} >> "$REPORT"

# 5) Loop log analysis (read-only)
section "AUTO LOOP LOG (last 200 lines)"
{
  if [ -f "$AUTOLOG" ]; then
    tail -n 200 "$AUTOLOG"
  else
    echo "(log file missing: $AUTOLOG)"
  fi
} >> "$REPORT"

section "SIGNAL SUMMARY FROM LOG"
{
  if [ -f "$AUTOLOG" ]; then
    echo "Counts by action:"
    grep -o '📈 Action: [A-Z]*' "$AUTOLOG" | awk '{print $3}' | sort | uniq -c | sort -nr || echo "(none)"
    echo
    echo "Last 5 actions:"
    grep '📈 Action:' "$AUTOLOG" | tail -n 5 || echo "(none)"
    echo
    echo "Last errors:"
    grep -E '✗|ERROR|Data quality failed' "$AUTOLOG" | tail -n 10 || echo "(none)"
    echo
    echo "Last loop stamps:"
    grep -E '^\[loop\] start|Entering hourly loop|Sleeping 3600s' "$AUTOLOG" | tail -n 12 || echo "(sparse)"
  else
    echo "(no log to analyze)"
  fi
} >> "$REPORT"

# 6) File integrity snapshot (no modification; new snapshot for diff)
section "FILE INTEGRITY (sha256)"
{
  echo "Computing sha256 for critical files…"
  CRIT=(
    "tools/auto_h1.sh"
    "tools/start_botA.sh"
    "tools/runner_confluence.py"
    "tools/tg_send.py"
    "data/ohlcv.py"
  )
  : > "$SNAPSHOT_NEW"
  for rel in "${CRIT[@]}"; do
    f="$PROJECT_ROOT/$rel"
    if [ -f "$f" ]; then
      sum="$(sha256sum "$f" 2>/dev/null | awk '{print $1}')"
      echo "$sum  $rel" | tee -a "$SNAPSHOT_NEW" >/dev/null
    else
      echo "MISSING       $rel" | tee -a "$SNAPSHOT_NEW" >/dev/null
    fi
  done

  if [ -f "$SNAPSHOT" ]; then
    echo -e "\nDiff vs previous snapshot ($SNAPSHOT):"
    diff -u "$SNAPSHOT" "$SNAPSHOT_NEW" || true
  else
    echo "No previous snapshot to compare."
  fi

  echo -e "\n(Next time you run this, it will compare to today’s snapshot.)"
} >> "$REPORT"

# 7) Optional ONLINE checks (off by default; require ONLINE=1)
if [ "$ONLINE" = "1" ]; then
  section "OPTIONAL ONLINE CHECKS (explicitly allowed)"
  {
    if [ -f "$ENVFILE" ]; then
      # shellcheck disable=SC1090
      set -a; source "$ENVFILE"; set +a
      echo "Attempting Telegram getMe (masked token)…"
      if command -v curl >/dev/null 2>&1 && [ -n "${BOT_TOKEN:-}" ]; then
        curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | head -c 600; echo
      else
        echo "(curl or BOT_TOKEN missing)"
      fi
      echo
      echo "Skipping TwelveData test (can add if you want)."
    else
      echo "(env missing; cannot run online checks)"
    fi
  } >> "$REPORT"
fi

# 8) Questions for the reviewing AI
section "QUESTIONS FOR AI REVIEWER"
{
  echo "1) From ACTION counts and timestamps, does signal cadence match 1h expectations?"
  echo "2) Do log errors (if any) suggest data feed hiccups that require retry/backoff (read-only suggestion)?"
  echo "3) Based on last few decisions, does SMA20 rule appear consistent with last_close vs SMA20 deltas printed?"
  echo "4) Any drift between file hashes compared to previous snapshot that might indicate accidental edits?"
  echo "5) Are tmux session cwd/cmd values correct and stable? Any sign of bare 'bash' lingering without our script?"
  echo "6) Is log freshness (last lines) within expected recency given sleep windows?"
  echo "7) Do you need additional artifacts (specific files, longer log window, config) to deepen the audit?"
} >> "$REPORT"

# Do NOT overwrite the baseline snapshot automatically; keep read-only behavior.
# If the operator explicitly wants to refresh baseline later:
# cp "$SNAPSHOT_NEW" "$SNAPSHOT"

echo -e "\nDONE. Report written to: $REPORT"
