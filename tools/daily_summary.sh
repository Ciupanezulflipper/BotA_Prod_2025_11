#!/usr/bin/env bash
set -euo pipefail

# --- Paths --------------------------------------------------------------------
ROOT="${HOME}/BotA"
LOGDIR="${ROOT}/logs"
CFGDIR="${ROOT}/config"
DOTENV="${ROOT}/.env"
SIGENV="${CFGDIR}/signal.env"
mkdir -p "${LOGDIR}"

# --- Env loaders --------------------------------------------------------------
load_env_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  # shellcheck disable=SC2162
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# || "$line" != *"="* ]] && continue
    key="${line%%=*}"; val="${line#*=}"
    # Do not override if already exported in the shell
    [[ -z "${!key-}" ]] && export "${key}=${val}"
  done < "$f"
}
load_env_file "$DOTENV"
load_env_file "$SIGENV"

# --- Helpers ------------------------------------------------------------------
ts() { date -u +'%Y-%m-%d %H:%M:%S UTC'; }
today() { date -u +'%Y-%m-%d'; }

# Safest send: plain text (no parse_mode) to avoid Telegram HTML entity errors
tg_send_plain() {
  local chat_id="${TELEGRAM_CHAT_ID-}"
  local bot="${TELEGRAM_BOT_TOKEN-}"
  local text="$1"
  [[ -n "$chat_id" && -n "$bot" ]] || { echo "[daily] ⚠️ TELEGRAM_* env missing"; return 0; }
  local api="https://api.telegram.org/bot${bot}/sendMessage"
  curl -sS -X POST "$api" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "disable_web_page_preview=true" \
    --data-urlencode "text=${text}" >/dev/null || true
}

# Count CSV rows where the first column (ts_utc) starts with today's date (UTC)
count_today_rows() {
  local file="$1"
  [[ -f "$file" ]] || { echo 0; return; }
  # Skip header; match date prefix in first column
  awk -F',' -v D="$(today)" 'NR>1 && index($1, D)==1 {c++} END{print c+0}' "$file"
}

# Extract last N human lines from accuracy.csv as bullets
last_accuracy_lines() {
  local file="$1" ; local n="$2"
  [[ -f "$file" ]] || return 0
  # Expected columns: ts_alert,pair,dir,entry_price,window_min,exit_price,pips,outcome,rsi_h1,m5,news,source,ts_eval
  # Show: - EURUSD BUY 30m: HIT | +12.3 pips (eval 12:34 UTC)
  tail -n +2 "$file" | tail -n "$n" | awk -F',' '
    function fmt_pips(p){ if (p ~ /^-?([0-9]+)(\.[0-9]+)?$/) {printf("%+.1f", p);} else {printf("%s", p);} }
    {
      pair=$2; dir=$3; win=$5; pips=$7; out=$8; te=$13;
      gsub(/ UTC$/,"",te);
      split(te, a, /[ T]/); t=a[2];
      printf("- %s %s %sm: %s | ", pair, dir, win, out);
      fmt_pips(pips); printf(" pips (eval %s UTC)\n", t);
    }'
}

# Compute daily hit/miss/neutral and hit-rate
compute_accuracy_summary() {
  local file="$1"
  local D="$(today)"
  [[ -f "$file" ]] || { echo "0 0 0 0.0"; return; }
  awk -F',' -v D="$D" '
    BEGIN{hit=miss=neu=0}
    NR>1 && index($13, D)==1 {
      if ($8=="HIT") hit++;
      else if ($8=="MISS") miss++;
      else neu++;
    }
    END{
      tot=hit+miss;
      rate=(tot>0)? (100.0*hit/tot) : 0.0;
      printf("%d %d %d %.2f", hit, miss, neu, rate);
    }' "$file"
}

# --- Build summary ------------------------------------------------------------
ALERTS_CSV="${LOGDIR}/alerts.csv"
ACCURACY_CSV="${LOGDIR}/accuracy.csv"

TODAY="$(today)"
ALERTS_TODAY="$(count_today_rows "$ALERTS_CSV")"

read HIT MISS NEU RATE <<<"$(compute_accuracy_summary "$ACCURACY_CSV")"

# Pull up to last 5 evaluated lines for quick context
LAST5="$(last_accuracy_lines "$ACCURACY_CSV" 5)"

SUMMARY=$(
  printf "📊 Daily Summary — %s\n" "$TODAY"
  printf "⏱  Generated: %s\n" "$(ts)"
  printf "✉️  Alerts sent today: %s\n" "$ALERTS_TODAY"
  printf "🎯 Accuracy today: %s HIT / %s MISS / %s NEUTRAL — Hit-rate: %.2f%%\n" "$HIT" "$MISS" "$NEU" "$RATE"
  if [[ -n "$LAST5" ]]; then
    printf "🧪 Last results:\n%s" "$LAST5"
  else
    printf "🧪 Last results:\n- (no evaluations yet today)"
  fi
)

# --- Output & Notify ----------------------------------------------------------
echo "$SUMMARY"
tg_send_plain "$SUMMARY"

# Also log to file for traceability
echo "[$(ts)] SUMMARY SENT
$SUMMARY
" >> "${LOGDIR}/daily_summary.log"

exit 0
