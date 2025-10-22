#!/usr/bin/env bash
set -eu

# --- config/paths ---
HOME_DIR="$HOME/TomaMobileForexBot"
LOGDIR="$HOME_DIR/logs"
PIDFILE="$HOME_DIR/scalper_watch.pid"
ERRLOG="$LOGDIR/errors.log"
SIGCSV="$LOGDIR/signals.csv"
OUT="$LOGDIR/health_$(date -u +%Y-%m-%d).log"

mkdir -p "$LOGDIR"

# --- env (Telegram + API keys for Python quote check) ---
set +e
[ -f "$HOME/.env" ] && . "$HOME/.env"
set -e
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

utc_now() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }
ts_24h_ago() { date -u -d '24 hours ago' +'%Y-%m-%dT%H:%M:%SZ'; }

# --- process status ---
PROC="stopped"
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE" || true)
  if [ -n "${PID:-}" ] && ps -p "$PID" >/dev/null 2>&1; then
    PROC="running (pid $PID)"
  else
    PROC="not running"
  fi
else
  PROC="no pid file"
fi

# --- signals last 24h (counts per pair/side) ---
SIG_SUM=$(awk -v TS="$(ts_24h_ago)" -F, '
BEGIN { buyE=0; selE=0; buyU=0; selU=0; }
NR==1 { next }    # header
{
    # csv: ts_utc,symbol,side,price,atr,sl,tp, ... ,provider=...
    t=$1; pair=$2; side=$3;
    if (t>=TS) {
        if (pair=="EURUSD" && side=="BUY")  buyE++;
        if (pair=="EURUSD" && side=="SELL") selE++;
        if (pair=="USDJPY" && side=="BUY")  buyU++;
        if (pair=="USDJPY" && side=="SELL") selU++;
    }
}
END {
    printf "EURUSD  BUY=%d  SELL=%d\n", buyE, selE;
    printf "USDJPY  BUY=%d  SELL=%d\n", buyU, selU;
}' "$SIGCSV" 2>/dev/null || echo "EURUSD  BUY=0  SELL=0"$'\n'"USDJPY  BUY=0  SELL=0")

# --- soft errors last 24h (missing-data) ---
ERRS=$(awk -v TS="$(ts_24h_ago)" '
$0 ~ /"missing data/ {
  # crude ISO/lexicographic guard: look for ts":"YYYY-MM-DDTHH:MM:SS
  m = match($0, /"ts": *"([0-9\-:T]+)"/, a);
  if (m && a[1] >= TS) c++
}
END { print (c ? c : 0) }' "$ERRLOG" 2>/dev/null || echo 0)

# --- quick last-quote snapshot (via Python, uses our data_providers) ---
PY_SNAP="$(python3 - <<'PY'
from data_providers import fetch_quote
for s in ("EURUSD","USDJPY"):
    prov, px = fetch_quote(s)
    print(f"{s:7s}: {prov or 'None'} px={px}")
PY
)"
# --- compose report ---
STAMP="$(utc_now)"
{
  echo "===== Daily Bot Health (UTC) @ $STAMP ====="
  echo "Process      : $PROC"
  echo "Signals 24h  :"
  echo "$SIG_SUM"
  echo "Soft-errors  : missing-data rows = $ERRS"
  echo "Snapshot     :"
  echo "$PY_SNAP"
} | tee "$OUT"

# --- Telegram push (optional) ---
if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
  TEXT=$(printf "%s\n%s\n%s\n%s\n%s\n%s\n%s\n" \
    "===== Daily Bot Health (UTC) @ $STAMP =====" \
    "Process: $PROC" \
    "Signals 24h:" \
    "$SIG_SUM" \
    "Soft-errors: missing-data rows = $ERRS" \
    "Snapshot:" \
    "$PY_SNAP" )
  # url-encode newlines as %0A (basic encoding)
  TEXT_ESC=$(printf "%s" "$TEXT" | sed ':a;N;$!ba;s/\n/%0A/g')
  curl -sS "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=$TEXT_ESC" \
    -d "disable_web_page_preview=true" >/dev/null 2>&1 && \
    echo "Telegram: sent ✅" || echo "Telegram: failed ❌"
else
  echo "Telegram: skipped (missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
fi
