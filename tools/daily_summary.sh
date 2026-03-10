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
TRADES_CSV="${LOGDIR}/trades.csv"

TODAY="$(today)"
ALERTS_TODAY="$(count_today_rows "$ALERTS_CSV")"

# Compute trade stats from trades.csv using Python
TRADE_STATS="$(BOTA_ROOT="${ROOT}" python3 - <<PY
import csv, os, sys
from datetime import datetime, timezone

ROOT = os.path.expanduser(os.environ.get("BOTA_ROOT", "~/BotA"))
TRADES = os.path.join(ROOT, "logs", "trades.csv")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

wins = losses = pending = 0
pips_list = []
score_list = []
pair_counts = {}

try:
    with open(TRADES, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = (row.get("timestamp") or "")[:10]
            if ts != TODAY:
                continue
            outcome = (row.get("outcome") or "").strip().upper()
            pair = (row.get("pair") or "").strip()
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            else:
                pending += 1
            try:
                pips_list.append(float(row.get("pips") or 0))
            except Exception:
                pass
            try:
                score_list.append(float(row.get("score") or 0))
            except Exception:
                pass
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
except FileNotFoundError:
    print("0|0|0|0|0.0|0.0|0.0|none")
    sys.exit(0)

total = wins + losses
wr = (wins / total * 100) if total > 0 else 0.0
avg_pips = (sum(pips_list) / len(pips_list)) if pips_list else 0.0
avg_score = (sum(score_list) / len(score_list)) if score_list else 0.0
pair_str = " ".join(f"{p}:{c}" for p, c in sorted(pair_counts.items()))
print(f"{total+pending}|{wins}|{losses}|{pending}|{wr:.1f}|{avg_pips:.1f}|{avg_score:.1f}|{pair_str or 'none'}")
PY
)"

IFS='|' read -r trades_today win loss pending wr avg_pips avg_score pairs <<< "${TRADE_STATS}"

SUMMARY=$(
  printf "📊 BotA Daily Summary — %s\n" "$TODAY"
  printf "⏱  Generated: %s\n" "$(ts)"
  printf "✉️  Alerts sent today: %s\n" "$ALERTS_TODAY"
  printf "📈 Trades today: %s (WIN=%s LOSS=%s PENDING=%s)\n" "$trades_today" "$win" "$loss" "$pending"
  printf "🎯 Win rate: %s%% | Avg pips: %s | Avg score: %s\n" "$wr" "$avg_pips" "$avg_score"
  printf "💱 Pairs: %s\n" "$pairs"
)

echo "$SUMMARY"
tg_send_plain "$SUMMARY"

echo "[$(ts)] SUMMARY SENT
$SUMMARY
" >> "${LOGDIR}/daily_summary.log"

exit 0
