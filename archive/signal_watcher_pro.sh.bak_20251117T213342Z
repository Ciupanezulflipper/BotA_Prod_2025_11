#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/signal_watcher_pro.sh
# PURPOSE: Watch pairs → fetch → score → (optional) Telegram alert + hourly logs
# USAGE: tools/signal_watcher_pro.sh [--once]

set -euo pipefail

# Robust path resolution
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Load static config
set -a
source config/strategy.env
set +a

# Optional dynamic overrides
[[ -f config/dynamic.env ]] && { set -a; source config/dynamic.env; set +a; }

# Validate
[[ -z "${PAIRS:-}"       ]] && { echo "ERROR: PAIRS not set" >&2; exit 1; }
[[ -z "${TIMEFRAMES:-}"  ]] && { echo "ERROR: TIMEFRAMES not set" >&2; exit 1; }
[[ -z "${ALERTS_CSV:-}"  ]] && { echo "ERROR: ALERTS_CSV not set" >&2; exit 1; }

# Normalize paths / ensure dirs
[[ "$ALERTS_CSV" != /* ]] && ALERTS_CSV="$ROOT_DIR/$ALERTS_CSV"
mkdir -p "$(dirname "$ALERTS_CSV")" cache logs

SLEEP="${WATCHER_SLEEP:-120}"
echo "[WATCHER $(date -Iseconds)] SANITY: PAIRS=\"$PAIRS\" TIMEFRAMES=\"$TIMEFRAMES\" ALERTS_CSV=\"$ALERTS_CSV\" SLEEP=\"${SLEEP}s\""

# Create alerts header if new
[[ ! -f "$ALERTS_CSV" ]] && echo "timestamp,pair,timeframe,verdict,score,confidence,reasons,price,provider" > "$ALERTS_CSV"

# Market hours (Forex Mon–Fri UTC)
is_market_open() {
  local dow; dow="$(date -u +%u)"   # 1=Mon .. 7=Sun
  if [[ "$dow" -eq 6 || "$dow" -eq 7 ]]; then
    echo "Closed"; return 1
  fi
  echo "Open"; return 0
}

# Live price probe (Yahoo v11 → v8 fallback)
probe_live_price() {
  local pair="$1" symbol="${pair}=X" price url
  url="https://query2.finance.yahoo.com/v11/finance/quoteSummary/${symbol}?modules=price"
  price="$(curl -sSL -H "User-Agent: Mozilla/5.0" "$url" | jq -r '.quoteSummary.result[0].price.regularMarketPrice.raw // 0' 2>/dev/null || echo 0)"
  if [[ "$price" == "0" || -z "$price" ]]; then
    url="https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1m&range=1d"
    price="$(curl -sSL -H "User-Agent: Mozilla/5.0" "$url" | jq -r '.chart.result[0].meta.regularMarketPrice // 0' 2>/dev/null || echo 0)"
  fi
  [[ "$price" == "0" || -z "$price" ]] && return 1
  echo "$price"; return 0
}

# Telegram helper
send_telegram() {
  local msg="$1"
  [[ "${TELEGRAM_ENABLED:-0}" != "1" ]] && return 0
  [[ -z "${TELEGRAM_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]] && return 0
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=${msg}" -d "parse_mode=${TELEGRAM_PARSE_MODE:-Markdown}" >/dev/null 2>&1 || true
}

# Battery-aware sleep
calc_sleep_battery_aware() {
  local pct status base sleepv
  base="${WATCHER_SLEEP:-120}"
  pct="$(termux-battery-status 2>/dev/null | jq -r '.percentage // 100' || echo 100)"
  status="$(termux-battery-status 2>/dev/null | jq -r '.status // "CHARGING"' || echo CHARGING)"
  sleepv="$base"
  if [[ "$pct" =~ ^[0-9]+$ ]] && [[ "$pct" -lt 30 ]] && [[ "$status" != "CHARGING" ]]; then
    sleepv=300
    echo "[BATTERY $(date -Iseconds)] Low battery (${pct}%), auto-slow to ${sleepv}s" >&2
  fi
  echo "$sleepv"
}

# Scan one pair/timeframe
scan_pair() {
  local p="$1" tf="${2:-H1}" cache_json="cache/${p}.json" cache_txt="cache/${p}.txt" provider_file="cache/${p}_provider.txt"
  local cache_age=9999
  if [[ -f "$cache_json" ]]; then
    local mtime
    mtime="$(stat -c %Y "$cache_json" 2>/dev/null || stat -f %m "$cache_json" 2>/dev/null || echo 0)"
    cache_age="$(( $(date +%s) - mtime ))"
  fi

  # Refresh candles if stale (>120s)
  if [[ "$cache_age" -gt 120 ]]; then
    echo "[FETCH $(date -Iseconds)] $p stale (${cache_age}s)"
    if [[ -f tools/data_fetch_candles.sh ]]; then
      bash tools/data_fetch_candles.sh "$p" "$tf" || return 1
    else
      echo "[WARN] data_fetch_candles.sh missing"; return 1
    fi
  else
    echo "[CACHE $(date -Iseconds)] $p fresh (${cache_age}s)"
  fi

  # Score via scoring_engine.sh
  if [[ ! -f tools/scoring_engine.sh ]]; then
    echo "[WARN] scoring_engine.sh missing → smoke row"
    echo "$(date -Iseconds),$p,$tf,HOLD,50,50,smoke,0.0,smoke" >> "$ALERTS_CSV"
    return 0
  fi

  local result score verdict conf reasons price provider
  result="$(bash tools/scoring_engine.sh "$p" "$tf" 2>/dev/null || echo '{"score":0,"verdict":"HOLD","confidence":50,"reasons":"error","price":0,"provider":"unknown"}')"
  score="$(echo "$result"   | jq -r '.score // 0'        2>/dev/null || echo 0)"
  verdict="$(echo "$result" | jq -r '.verdict // "HOLD"' 2>/dev/null || echo HOLD)"
  conf="$(echo "$result"    | jq -r '.confidence // 50'  2>/dev/null || echo 50)"
  reasons="$(echo "$result" | jq -r '.reasons // "n/a"'  2>/dev/null || echo n/a)"
  price="$(echo "$result"   | jq -r '.price // 0'        2>/dev/null || echo 0)"
  provider="$(echo "$result"| jq -r '.provider // "unknown"' 2>/dev/null || echo unknown)"

  # Live price probe (non-blocking)
  probe_live_price "$p" >/dev/null 2>&1 && echo "[LIVE $(date -Iseconds)] $p live probe OK"

  # Emit alert row + optional Telegram
  local ts min_score
  ts="$(date -Iseconds)"; min_score="${TELEGRAM_MIN_SCORE:-70}"
  if [[ "$verdict" != "HOLD" || "$score" -ge 65 ]]; then
    echo "$ts,$p,$tf,$verdict,$score,$conf,$reasons,$price,$provider" >> "$ALERTS_CSV"
    echo "[ALERT $ts] $p $tf $verdict score=$score conf=$conf price=$price prov=$provider"
    if [[ "${TELEGRAM_ENABLED:-0}" == "1" && "$score" -ge "$min_score" ]]; then
      send_telegram "🤖 *BotA Signal*\n*Pair:* $p\n*TF:* $tf\n*Verdict:* $verdict\n*Score:* $score\n*Price:* $price"
    fi
  else
    echo "[SKIP $(date -Iseconds)] $p $tf score=$score verdict=$verdict"
  fi
}

log_sanity(){ echo "[SANITY $(date -Iseconds)] PAIRS=$PAIRS TF=$TIMEFRAMES CSV=$ALERTS_CSV SLEEP=${SLEEP}s"; }

# Market phase banner
echo "[MARKET $(date -Iseconds)] phase: $(is_market_open || echo Closed)"

# Single scan mode
if [[ "${1:-}" == "--once" ]]; then
  log_sanity
  IFS=' ' read -ra PAIR_ARR <<< "$PAIRS"
  IFS=' ' read -ra TF_ARR   <<< "$TIMEFRAMES"
  for p in "${PAIR_ARR[@]}"; do
    for tf in "${TF_ARR[@]}"; do
      scan_pair "$p" "$tf" || true
    done
  done
  echo "[DONE $(date -Iseconds)] manual --once scan complete"
  exit 0
fi

# Continuous loop
echo "[MODE $(date -Iseconds)] Continuous watch"
while true; do
  [[ -f config/dynamic.env ]] && { set -a; source config/dynamic.env; set +a; }
  log_sanity

  if ! is_market_open >/dev/null; then
    echo "[IDLE $(date -Iseconds)] Market closed, sleeping 300s"
    echo "$(date +%s)" > cache/watcher.heartbeat 2>/dev/null || true
    sleep 300; continue
  fi

  IFS=' ' read -ra PAIR_ARR <<< "$PAIRS"
  IFS=' ' read -ra TF_ARR   <<< "$TIMEFRAMES"
  for p in "${PAIR_ARR[@]}"; do
    for tf in "${TF_ARR[@]}"; do
      scan_pair "$p" "$tf" || true
    done
  done

  echo "$(date +%s)" > cache/watcher.heartbeat 2>/dev/null || true
  sleep "$(calc_sleep_battery_aware)"
done
