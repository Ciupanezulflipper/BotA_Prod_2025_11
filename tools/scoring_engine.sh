# FILE: tools/scoring_engine.sh
# MODE: A (market-closed = immediate HOLD)
# CONTRACT:
#   usage: bash tools/scoring_engine.sh <PAIR> <TIMEFRAME> [provider]
#   stdout JSON: {"score": <0-100>,"verdict":"BUY|SELL|HOLD","confidence":<0-100>,
#                 "reasons":"...", "price":"", "provider":"<provider>"}
# NOTES:
#   - Zero external secrets; reads config/strategy.env (weights, thresholds).
#   - If market is not Open -> emits HOLD immediately (no fetching).
#   - Uses cached indicator JSON if present: cache/indicators_${PAIR}_${TF}.json
#     (keys: ema9, ema21, rsi, macd_hist, adx, pattern, price).
#   - Fully bc-free; sanitizes all numeric fields and guards jq.
#   - Safe to run on Termux/Android 15.

#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="${HOME}/BotA"
CFG="${ROOT}/config/strategy.env"
TOOLS="${ROOT}/tools"
CACHE="${ROOT}/cache"

PAIR="${1:-EURUSD}"
TF="${2:-H1}"
PROVIDER="${3:-yahoo}"

mkdir -p "${CACHE}"

# ---------- helpers ----------
log() { printf '%s\n' "$*" >&2; }
jq_safe() { jq -r "$1" 2>/dev/null || printf ''; }
num_sanitize() {
  # strips everything except digits, minus, and dot; empty -> 0
  local v="${1:-}"; v="${v//,/}"
  v="$(printf '%s' "$v" | sed 's/[^0-9.+-]//g')"
  if [[ -z "$v" || "$v" == "." || "$v" == "-" || "$v" == "+" ]]; then
    printf '0'
  else
    printf '%s' "$v"
  fi
}
fcalc() {
  # portable float math via awk
  awk -v a="$1" -v b="$2" -v op="$3" 'BEGIN{
    if (op=="+") printf("%.6f", a+b);
    else if (op=="-") printf("%.6f", a-b);
    else if (op=="*") printf("%.6f", a*b);
    else if (op=="/") { if (b==0) printf("0"); else printf("%.6f", a/b); }
    else printf("0");
  }'
}
clamp01() {
  awk -v x="$1" 'BEGIN{ if(x<0) x=0; if(x>1) x=1; printf("%.6f", x); }'
}
pct() { # 0..100
  awk -v x="$1" 'BEGIN{ if(x<0) x=0; if(x>100) x=100; printf("%d", x+0.5) }'
}

# ---------- config (no secrets printed) ----------
TELEGRAM_MIN_SCORE="65"
WEIGHT_TREND="40"
WEIGHT_MOMENTUM="30"
WEIGHT_RSI="20"
WEIGHT_FILTERS="10"

if [[ -f "${CFG}" ]]; then
  # shellcheck disable=SC1090
  source "${CFG}"
fi

# ---------- market gate (MODE A) ----------
PHASE="Unknown"
if [[ -x "${TOOLS}/market_open.sh" ]]; then
  PHASE="$("${TOOLS}/market_open.sh" 2>/dev/null || echo "Unknown")"
fi

if [[ "${PHASE}" != "Open" ]]; then
  # Immediate HOLD without fetching/scoring
  jq -n \
    --arg v "HOLD" \
    --arg c "0" \
    --arg r "market_closed" \
    --arg p "" \
    --arg prov "${PROVIDER}" \
    '{score:0, verdict:$v, confidence:($c|tonumber),
      reasons:$r, price:$p, provider:$prov}'
  exit 0
fi

# ---------- load indicators (cached JSON if available) ----------
J="${CACHE}/indicators_${PAIR}_${TF}.json"
price=""
ema9="0"; ema21="0"; rsi="0"; macd_hist="0"; adx="0"; pattern="none"

if [[ -s "${J}" ]]; then
  raw="$(cat "${J}")"
  ema9="$(num_sanitize "$(jq_safe '.ema9 // 0' <<<"$raw")")"
  ema21="$(num_sanitize "$(jq_safe '.ema21 // 0' <<<"$raw")")"
  rsi="$(num_sanitize "$(jq_safe '.rsi // 0' <<<"$raw")")"
  macd_hist="$(num_sanitize "$(jq_safe '.macd_hist // 0' <<<"$raw")")"
  adx="$(num_sanitize "$(jq_safe '.adx // 0' <<<"$raw")")"
  pattern="$(jq_safe '.pattern // "none"' <<<"$raw")"
  price="$(jq_safe '.price // ""' <<<"$raw")"
fi

# ---------- scoring (bc-free, fully sanitized) ----------
# Trend: EMA9 vs EMA21 (+1 bullish, -1 bearish, 0 flat)
trend_raw="0"
cmp="$(awk -v e9="$ema9" -v e21="$ema21" 'BEGIN{ if (e9>e21) print 1; else if (e9<e21) print -1; else print 0 }')"
trend_raw="$cmp"

# Momentum: MACD histogram sign (+1 bullish, -1 bearish, 0 flat)
mom_raw="$(awk -v h="$macd_hist" 'BEGIN{ if (h>0) print 1; else if (h<0) print -1; else print 0 }')"

# RSI contribution: scaled from 30..70 into -1..+1 (clamped)
rsi_pos="$(awk -v r="$rsi" 'BEGIN{
  # center 50 -> 0; 70 -> +1; 30 -> -1
  val=(r-50)/20.0; if (val>1) val=1; if (val<-1) val=-1; printf("%.6f", val)
}')"

# Filters: ADX trend strength 0..1 (>=25 treated as good)
adx_f="$(awk -v a="$adx" 'BEGIN{ v=a/50.0; if(v>1)v=1; if(v<0)v=0; printf("%.6f", v) }')"

# Pattern flag: simple boost if pattern looks bullish/bearish keywords present
pat="0"
lower_pat="$(printf '%s' "${pattern,,}")"
if printf '%s' "$lower_pat" | grep -Eq 'hammer|bull|engulfing|piercing'; then
  pat="0.2"
elif printf '%s' "$lower_pat" | grep -Eq 'shooting|bear|dark cloud|hanging'; then
  pat="-0.2"
fi

# Normalize weights to 1.0
W_T="$(awk -v a="$WEIGHT_TREND" -v b="$WEIGHT_MOMENTUM" -v c="$WEIGHT_RSI" -v d="$WEIGHT_FILTERS" 'BEGIN{ s=a+b+c+d; if(s==0){print "0 0 0 0 1"} else {print a/s, b/s, c/s, d/s, s}}')"
WT="$(echo "$W_T" | awk '{print $1}')"
WM="$(echo "$W_T" | awk '{print $2}')"
WR="$(echo "$W_T" | awk '{print $3}')"
WF="$(echo "$W_T" | awk '{print $4}')"

# Weighted sum in -1..+1
sum1="$(awk -v t="$trend_raw" -v m="$mom_raw" -v r="$rsi_pos" -v f="$adx_f" -v p="$pat" -v wt="$WT" -v wm="$WM" -v wr="$WR" -v wf="$WF" 'BEGIN{
  # include small pattern weight inside filters component
  val = (t*wt) + (m*wm) + (r*wr) + ((f + p)/1.2)*wf;
  if (val>1) val=1; if (val<-1) val=-1; printf("%.6f", val)
}')"

# Map -1..+1 -> 0..100
score="$(awk -v v="$sum1" 'BEGIN{ s=(v+1)*50; if(s<0)s=0; if(s>100)s=100; printf("%d", s+0.5) }')"

# Verdict thresholds
verdict="HOLD"
if (( score >= 65 )); then
  verdict="BUY"
elif (( score <= 35 )); then
  verdict="SELL"
fi

# Confidence same as score (0..100)
confidence="$score"

# Reasons string (compact)
reason_parts=()
if (( trend_raw > 0 )); then reason_parts+=("EMA9>EMA21"); elif (( trend_raw < 0 )); then reason_parts+=("EMA9<EMA21"); else reason_parts+=("EMA flat"); fi
if (( mom_raw > 0 )); then reason_parts+=("MACD_up"); elif (( mom_raw < 0 )); then reason_parts+=("MACD_down"); else reason_parts+=("MACD_flat"); fi
reason_parts+=("RSI=$(printf '%.1f' "$rsi")")
reason_parts+=("ADX=$(printf '%.1f' "$adx")")
[[ "$pattern" != "none" && -n "$pattern" ]] && reason_parts+=("pattern:${pattern}")
reasons="$(IFS=';'; echo "${reason_parts[*]}")"

# ---------- emit JSON ----------
jq -n \
  --argjson s "$score" \
  --arg v "$verdict" \
  --argjson c "$confidence" \
  --arg r "$reasons" \
  --arg p "$price" \
  --arg prov "$PROVIDER" \
  '{score:$s, verdict:$v, confidence:$c, reasons:$r, price:$p, provider:$prov}'
