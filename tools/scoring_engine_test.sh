#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/scoring_engine_test.sh
# PURPOSE: Test scoring with cached indicators while market is closed.
# CONTRACT:
#   usage: bash tools/scoring_engine_test.sh <PAIR> <TIMEFRAME> [provider]
#   stdout JSON: {score, verdict, confidence, reasons, price, provider}

set -euo pipefail

ROOT="${HOME}/BotA"
CFG="${ROOT}/config/strategy.env"
CACHE="${ROOT}/cache"

PAIR="${1:-EURUSD}"
TF="${2:-H1}"
PROVIDER="${3:-test}"

mkdir -p "${CACHE}"

# ---------- helpers ----------
jq_safe(){ jq -r "$1" 2>/dev/null || printf ''; }
num_sanitize(){
  local v="${1:-}"; v="${v//,/}"
  v="$(printf '%s' "$v" | sed 's/[^0-9.+-]//g')"
  [[ -z "$v" || "$v" == "." || "$v" == "-" || "$v" == "+" ]] && printf '0' || printf '%s' "$v"
}

# ---------- config ----------
TELEGRAM_MIN_SCORE="65"
WEIGHT_TREND="40"
WEIGHT_MOMENTUM="30"
WEIGHT_RSI="20"
WEIGHT_FILTERS="10"
[[ -f "${CFG}" ]] && source "${CFG}"

# ---------- load indicators (cached JSON required for test) ----------
J="${CACHE}/indicators_${PAIR}_${TF}_json"
if [[ ! -s "${J}" ]]; then
  jq -n --arg v "HOLD" --arg r "no_indicators" --arg p "" --arg prov "$PROVIDER" \
      '{score:50, verdict:$v, confidence:50, reasons:$r, price:$p, provider:$prov}'
  exit 0
fi

raw="$(cat "${J}")"
ema9="$(num_sanitize "$(jq_safe '.ema9 // 0' <<<"$raw")")"
ema21="$(num_sanitize "$(jq_safe '.ema21 // 0' <<<"$raw")")"
rsi="$(num_sanitize "$(jq_safe '.rsi // 50' <<<"$raw")")"
macd_hist="$(num_sanitize "$(jq_safe '.macd_hist // 0' <<<"$raw")")"
adx="$(num_sanitize "$(jq_safe '.adx // 0' <<<"$raw")")"
pattern="$(jq_safe '.pattern // "none"' <<<"$raw")"
price="$(jq_safe '.price // ""' <<<"$raw")"

# ---------- scoring (awk only) ----------
trend_raw="$(awk -v e9="$ema9" -v e21="$ema21" 'BEGIN{if(e9>e21)print 1; else if(e9<e21)print -1; else print 0}')"
mom_raw="$(awk -v h="$macd_hist" 'BEGIN{if(h>0)print 1; else if(h<0)print -1; else print 0}')"
rsi_pos="$(awk -v r="$rsi" 'BEGIN{v=(r-50)/20.0; if(v>1)v=1; if(v<-1)v=-1; printf("%.6f",v)}')"
adx_f="$(awk -v a="$adx" 'BEGIN{v=a/50.0; if(v>1)v=1; if(v<0)v=0; printf("%.6f",v)}')"

pat="0"
lp="$(printf '%s' "${pattern,,}")"
if printf '%s' "$lp" | grep -Eq 'hammer|bull|engulfing|piercing'; then pat="0.2"
elif printf '%s' "$lp" | grep -Eq 'shooting|bear|dark cloud|hanging'; then pat="-0.2"
fi

read WT WM WR WF _ <<<"$(awk -v a="$WEIGHT_TREND" -v b="$WEIGHT_MOMENTUM" -v c="$WEIGHT_RSI" -v d="$WEIGHT_FILTERS" 'BEGIN{s=a+b+c+d; if(s==0)s=1; printf("%.6f %.6f %.6f %.6f 0", a/s,b/s,c/s,d/s)}')"

sum1="$(awk -v t="$trend_raw" -v m="$mom_raw" -v r="$rsi_pos" -v f="$adx_f" -v p="$pat" -v wt="$WT" -v wm="$WM" -v wr="$WR" -v wf="$WF" 'BEGIN{
  v=(t*wt) + (m*wm) + (r*wr) + ((f+p)/1.2)*wf; if(v>1)v=1; if(v<-1)v=-1; printf("%.6f",v)
}')"
score="$(awk -v v="$sum1" 'BEGIN{s=(v+1)*50; if(s<0)s=0; if(s>100)s=100; printf("%d",s+0.5)}')"

verdict="HOLD"
if (( score >= 65 )); then verdict="BUY"
elif (( score <= 35 )); then verdict="SELL"; fi
confidence="$score"

reasons=()
if (( trend_raw>0 )); then reasons+=("EMA9>EMA21"); elif (( trend_raw<0 )); then reasons+=("EMA9<EMA21"); else reasons+=("EMA flat"); fi
if (( mom_raw>0 )); then reasons+=("MACD_up"); elif (( mom_raw<0 )); then reasons+=("MACD_down"); else reasons+=("MACD_flat"); fi
reasons+=("RSI=$(printf '%.1f' "$rsi")")
reasons+=("ADX=$(printf '%.1f' "$adx")")
[[ "$pattern" != "none" && -n "$pattern" ]] && reasons+=("pattern:${pattern}")
reason_str="$(IFS=';'; echo "${reasons[*]}")"

jq -n \
  --argjson s "$score" \
  --arg v "$verdict" \
  --argjson c "$confidence" \
  --arg r "$reason_str" \
  --arg p "$price" \
  --arg prov "$PROVIDER" \
  '{score:$s, verdict:$v, confidence:$c, reasons:$r, price:$p, provider:$prov}'
