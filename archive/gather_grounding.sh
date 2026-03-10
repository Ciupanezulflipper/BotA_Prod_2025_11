#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/gather_grounding.sh
# PURPOSE: Collect precise grounding so I can ship full, validated files next
#          (scorer + per-signal Telegram alerts) without guesswork.

set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
CFG="${ROOT}/config/strategy.env"

sep(){ printf "\n—— %s ——\n" "$*"; }

sep "1) Environment snapshot"
printf "cwd=%s\n" "$(pwd)"
printf "bash=%s\n" "$(command -v bash)"
printf "date_utc=%s\n" "$(date -u +%FT%TZ)"

sep "2) Strategy config flags (no secrets printed)"
if [[ -f "$CFG" ]]; then
  TELE_ON=$(grep -E '^TELEGRAM_ENABLED=' "$CFG" | cut -d= -f2-)
  DASH_ON=$(grep -E '^TELEGRAM_DASHBOARD=' "$CFG" | cut -d= -f2-)
  MIN_SCORE=$(grep -E '^TELEGRAM_MIN_SCORE=' "$CFG" | cut -d= -f2-)
  printf "TELEGRAM_ENABLED=%s\n" "${TELE_ON:-?}"
  printf "TELEGRAM_DASHBOARD=%s\n" "${DASH_ON:-?}"
  printf "TELEGRAM_MIN_SCORE=%s\n" "${MIN_SCORE:-?}"
  # Masked presence check (no secrets)
  TOK_OK=$(grep -E '^TELEGRAM_TOKEN=' "$CFG" >/dev/null 2>&1 && echo yes || echo no)
  CHAT_OK=$(grep -E '^TELEGRAM_CHAT_ID=' "$CFG" >/dev/null 2>&1 && echo yes || echo no)
  printf "TOKEN_present=%s CHAT_ID_present=%s\n" "$TOK_OK" "$CHAT_OK"
else
  echo "MISSING: $CFG"
fi

sep "3) Locate watcher/scorer entrypoint(s)"
ls -1 "$TOOLS" | grep -E 'signal_.*(watch|score).*|watcher.*\.sh' || true
# Show the canonical watcher if present
if [[ -f "$TOOLS/signal_watcher_pro.sh" ]]; then
  echo "[found] tools/signal_watcher_pro.sh"
  # Show call-sites that would gate Telegram alerts / scoring
  grep -nE 'TELEGRAM_MIN_SCORE|send_telegram|score|alerts\.csv' "$TOOLS/signal_watcher_pro.sh" || true
fi
# Look for a dedicated scorer script if any
if ls "$TOOLS"/signal_*score*.sh >/dev/null 2>&1; then
  echo "[found] scorer scripts:"
  ls -1 "$TOOLS"/signal_*score*.sh
fi

sep "4) alerts.csv header + last 5 lines (if exists)"
CSV_PATH="$(grep -E '^ALERTS_CSV=' "$CFG" 2>/dev/null | cut -d= -f2- | tr -d '"')"
echo "ALERTS_CSV=${CSV_PATH:-<unset>}"
if [[ -n "${CSV_PATH:-}" && -f "$CSV_PATH" ]]; then
  head -n 1 "$CSV_PATH" || true
  tail -n 5 "$CSV_PATH" || true
else
  echo "alerts.csv not found yet (this is OK)."
fi

sep "5) Heartbeat + dashboard tail (freshness signals)"
if [[ -f "$ROOT/cache/watcher.heartbeat" ]]; then
  AGE=$(( $(date +%s) - $(cat "$ROOT/cache/watcher.heartbeat" 2>/dev/null || echo $(date +%s)) ))
  printf "watcher_heartbeat_age=%ss\n" "$AGE"
else
  echo "no watcher heartbeat file"
fi
if [[ -f "$ROOT/logs/dashboard_hourly.txt" ]]; then
  tail -n 3 "$ROOT/logs/dashboard_hourly.txt" || true
else
  echo "no dashboard_hourly.txt yet"
fi

sep "6) Provider notes (helps me wire score breakdowns)"
# List any provider modules/scripts you use for prices/indicators
ls -1 "$TOOLS" | grep -Ei 'yahoo|price|ohlc|rsi|ema|macd|adx' || true

sep "END — paste this whole output back to me"
