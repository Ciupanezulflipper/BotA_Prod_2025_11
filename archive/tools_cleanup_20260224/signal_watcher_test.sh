#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/signal_watcher_test.sh
# PURPOSE: Send clean, human-readable TEST alerts to Telegram using cached indicators.
# CONTRACT:
#   bash tools/signal_watcher_test.sh [--once] [--dry]
# Notes:
#   • Uses scoring_engine_test.sh (no market check) and ONLY cached JSON in cache/indicators_*.json
#   • Reads TELEGRAM_* and TELEGRAM_MIN_SCORE from config/strategy.env
#   • Writes a concise log to logs/alerts_test.txt (no secrets)

set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
CFG="${ROOT}/config/strategy.env"
LOGS="${ROOT}/logs"
CACHE="${ROOT}/cache"

mkdir -p "$LOGS" "$CACHE"

# ---------------- Flags ----------------
ONCE=0
DRY=0
for a in "$@"; do
  case "$a" in
    --once) ONCE=1 ;;
    --dry) DRY=1 ;;
  esac
done

# ---------------- Config (no secrets printed) ----------------
TELEGRAM_ENABLED="1"
TELEGRAM_DASHBOARD="0"
TELEGRAM_MIN_SCORE="65"
if [[ -f "$CFG" ]]; then
  # shellcheck disable=SC1090
  source "$CFG"
fi

# Require token + chat id only when sending
require_telegram() {
  if [[ "${TELEGRAM_ENABLED:-0}" != "1" ]]; then return 1; fi
  [[ -n "${TELEGRAM_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]
}

# ---------------- Safe Telegram send ----------------
# Uses curl --data-urlencode so we don't manually escape % or newlines.
send_tg() {
  local msg="$1"
  [[ "$DRY" == "1" ]] && { echo "[DRY] TG: ${msg}" ; return 0; }
  require_telegram || { echo "[WARN] Telegram disabled or missing creds" >&2; return 0; }

  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    --data "parse_mode=Markdown" >/dev/null 2>&1 || true
}

# ---------------- Pretty message builder ----------------
# Renders a compact, readable alert with bold labels and symbols.
pretty_msg() {
  local pair="$1" tf="$2" verdict="$3" score="$4" conf="$5" price="$6" reason="$7" provider="$8" ts="$9"

  # Normalize reason list: replace semicolons with middle dots and tidy arrows
  local rr
  rr="$(printf "%s" "$reason" \
        | sed -e 's/;/ · /g' \
              -e 's/MACD_up/MACD↑/g' \
              -e 's/MACD_down/MACD↓/g' \
              -e 's/EMA9>EMA21/EMA9➜EMA21/g' \
              -e 's/EMA9<EMA21/EMA21➜EMA9/g' \
              -e 's/pattern:/pattern: /g' \
              -e 's/RSI=/RSI /g' \
              -e 's/ADX=/ADX /g')"

  cat <<MSG
🤖 *BotA Test Signal*
*Pair:* ${pair}   *TF:* ${tf}
*Verdict:* ${verdict}
*Score:* ${score}/100   (*Conf:* ${conf})
*Price:* ${price}
*Reason:* ${rr}
*Provider:* ${provider}
*time:* ${ts}
MSG
}

# ---------------- Scan logic ----------------
pairs=(EURUSD GBPUSD XAUUSD USDJPY NAS100)
tfs=(H1 H4 D1)

alerts=0
sent=0
now_utc="$(date -u +'%Y-%m-%d %H:%M:%SZ')"

scan_once() {
  for p in "${pairs[@]}"; do
    for tf in "${tfs[@]}"; do
      alerts=$((alerts+1))
      local j="${CACHE}/indicators_${p}_${tf}.json"
      if [[ ! -s "$j" ]]; then
        echo "[TEST ${now_utc}] ${p} ${tf} score=50 verdict=HOLD price=? reasons=no_indicators" >>"$LOGS/alerts_test.txt"
        continue
      fi

      # Run test scorer (no market gate)
      local out
      out="$(
        bash "${TOOLS}/scoring_engine_test.sh" "$p" "$tf" 2>/dev/null || echo '{}'
      )"

      local score verdict conf reasons price provider
      score="$(echo "$out" | jq -r '.score // 0')"
      verdict="$(echo "$out" | jq -r '.verdict // "HOLD"')"
      conf="$(echo "$out" | jq -r '.confidence // 0')"
      reasons="$(echo "$out" | jq -r '.reasons // ""')"
      price="$(echo "$out" | jq -r '.price // ""')"
      provider="$(echo "$out" | jq -r '.provider // "test"')"

      echo "[TEST ${now_utc}] ${p} ${tf} score=${score} verdict=${verdict} price=${price:-?} reasons=${reasons:-?}" >>"$LOGS/alerts_test.txt"

      if (( score >= TELEGRAM_MIN_SCORE )); then
        local msg
        msg="$(pretty_msg "$p" "$tf" "$verdict" "$score" "$conf" "${price:-?}" "${reasons:-?}" "${provider}" "${now_utc}")"
        send_tg "$msg"
        sent=$((sent+1))
      fi
    done
  done
  echo "[TEST SUMMARY] scanned=${alerts} sent=${sent} (min_score=${TELEGRAM_MIN_SCORE})"
}

# ---------------- Main ----------------
# Quick banner (no secrets)
echo "TELEGRAM_ENABLED=${TELEGRAM_ENABLED:-0} TELEGRAM_MIN_SCORE=${TELEGRAM_MIN_SCORE:-65}"

if [[ "$ONCE" == "1" ]]; then
  scan_once
else
  # Default behavior for this tester is a single pass
  scan_once
fi
