#!/usr/bin/env bash
###############################################################################
# FILE: tools/data_fetch_candles.sh
# ROLE: OANDA primary + Yahoo fallback with provider-specific request evidence.
###############################################################################
set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

CODE_ROOT="${BOTA_CODE_ROOT:-${BOTA_ROOT:-${HOME}/BotA}}"
MUTABLE_ROOT="${BOTA_MUTABLE_ROOT:-${CODE_ROOT}}"
ROOT="${CODE_ROOT}"
CACHE_DIR="${MUTABLE_ROOT}/cache"
DATA_DIR="${MUTABLE_ROOT}/data/candles"
TOOLS_DIR="${CODE_ROOT}/tools"
LOG_DIR="${MUTABLE_ROOT}/logs"
PROVIDER_USAGE="${TOOLS_DIR}/provider_usage.py"

if [[ "${BOTA_PATH_CONTRACT_CHECK:-0}" == 1 ]]; then
  printf 'CODE_ROOT=%s\nMUTABLE_ROOT=%s\nTOOLS=%s\nCACHE=%s\nDATA=%s\nLOGS=%s\n' \
    "${CODE_ROOT}" "${MUTABLE_ROOT}" "${TOOLS_DIR}" "${CACHE_DIR}" "${DATA_DIR}" "${LOG_DIR}"
  exit 0
fi

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT}/.env"
  set +a
fi

LEGACY_PAIR_CACHE_TF="${LEGACY_PAIR_CACHE_TF:-H1}"
UA="${UA:-Mozilla/5.0 (Linux; Android 13; Termux) AppleWebKit/537.36}"
OANDA_API_TOKEN="${OANDA_API_TOKEN:-}"
OANDA_API_URL="${OANDA_API_URL:-https://api-fxpractice.oanda.com}"

log() { printf '%s\n' "$*" >&2; }
die() { log "[FETCH] ERROR: $*"; exit 1; }

provider_record() {
  local provider="$1" status="$2" note="${3:-}"
  [[ -f "${PROVIDER_USAGE}" ]] || return 0
  python3 "${PROVIDER_USAGE}" record \
    --provider "${provider}" \
    --caller data_fetch_candles \
    --pair "${PAIR:-}" \
    --timeframe "${TF:-}" \
    --status "${status}" \
    --credits 0 \
    --note "${note}" \
    >/dev/null 2>>"${LOG_DIR}/error.log" || true
}

PAIR_RAW="${1:-}"
TF_RAW="${2:-}"
[[ -z "${PAIR_RAW}" || -z "${TF_RAW}" ]] && {
  log "Usage: $0 <PAIR> <TF>"
  exit 1
}

PAIR="$(printf '%s' "${PAIR_RAW}" | tr -d '/ ' | tr '[:lower:]' '[:upper:]')"
TF="$(printf '%s' "${TF_RAW}" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"

mkdir -p "${CACHE_DIR}" "${DATA_DIR}" "${LOG_DIR}" >/dev/null 2>&1 || true

tf_minutes() {
  local tf="${1:-}" digits=""
  tf="$(printf '%s' "${tf}" | tr '[:lower:]' '[:upper:]')"
  case "${tf}" in
    M*)
      digits="${tf#M}"
      case "${digits}" in
        ""|*[!0-9]*) ;;
        *) echo "${digits}"; return ;;
      esac
      ;;
    H*)
      digits="${tf#H}"
      case "${digits}" in
        ""|*[!0-9]*) ;;
        *) echo "$(( digits * 60 ))"; return ;;
      esac
      ;;
    D1|1D)
      echo "1440"
      return
      ;;
  esac
  echo "0"
}

expected_min="$(tf_minutes "${TF}")"
[[ "${expected_min}" -le 0 ]] && die "unsupported TF='${TF}'"

oanda_granularity_for_tf() {
  case "${1:-}" in
    M1) echo "M1" ;;
    M5) echo "M5" ;;
    M15) echo "M15" ;;
    M30) echo "M30" ;;
    H1) echo "H1" ;;
    H2) echo "H2" ;;
    H4) echo "H4" ;;
    H6) echo "H6" ;;
    H8) echo "H8" ;;
    H12) echo "H12" ;;
    D1|1D) echo "D" ;;
    *) echo "" ;;
  esac
}

yahoo_symbol_for_pair() {
  case "${1:-}" in
    EURUSD) echo "EURUSD=X" ;;
    GBPUSD) echo "GBPUSD=X" ;;
    USDJPY) echo "USDJPY=X" ;;
    AUDUSD) echo "AUDUSD=X" ;;
    USDCAD) echo "USDCAD=X" ;;
    USDCHF) echo "USDCHF=X" ;;
    NZDUSD) echo "NZDUSD=X" ;;
    XAUUSD) echo "XAUUSD=X" ;;
    *) [[ "${#1}" -eq 6 ]] && echo "${1}=X" || echo "${1}" ;;
  esac
}

yahoo_interval_for_tf() {
  case "${1:-}" in
    M1) echo "1m" ;;
    M5) echo "5m" ;;
    M15) echo "15m" ;;
    M30) echo "30m" ;;
    H1) echo "1h" ;;
    H4) echo "4h" ;;
    D1|1D) echo "1d" ;;
    *) echo "" ;;
  esac
}

yahoo_range_for_tf() {
  case "${1:-}" in
    M1|M2|M5) echo "1d" ;;
    M15|M30) echo "5d" ;;
    H1|H2|H4) echo "5d" ;;
    D1|1D) echo "1mo" ;;
    *) echo "2d" ;;
  esac
}

OUT_JSON="${CACHE_DIR}/${PAIR}_${TF}.json"
OUT_CSV="${DATA_DIR}/${PAIR}_${TF}.csv"
LEGACY_JSON="${CACHE_DIR}/${PAIR}.json"

TMP_JSON="$(mktemp 2>/dev/null || echo "${CACHE_DIR}/.tmp_fetch_${PAIR}_${TF}_$$.json")"
TMP_CSV="$(mktemp 2>/dev/null || echo "${DATA_DIR}/.tmp_fetch_${PAIR}_${TF}_$$.csv")"
cleanup() { rm -f "${TMP_JSON}" "${TMP_CSV}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

PROVIDER_USED=""
OANDA_GRAN="$(oanda_granularity_for_tf "${TF}")"
OANDA_INSTRUMENT="${PAIR:0:3}_${PAIR:3:3}"

if [[ -n "${OANDA_API_TOKEN}" && -n "${OANDA_GRAN}" ]]; then
  log "[FETCH] trying OANDA: instrument=${OANDA_INSTRUMENT} gran=${OANDA_GRAN}"
  OANDA_OK="$(
    OANDA_API_TOKEN="${OANDA_API_TOKEN}" OANDA_API_URL="${OANDA_API_URL}" \
    OANDA_INSTRUMENT="${OANDA_INSTRUMENT}" OANDA_GRAN="${OANDA_GRAN}" \
    TMP_JSON="${TMP_JSON}" python3 <<'PY' 2>>"${LOG_DIR}/error.log"
import datetime
import json
import os
import sys
import urllib.request

token = os.environ["OANDA_API_TOKEN"]
base = os.environ["OANDA_API_URL"].rstrip("/")
inst = os.environ["OANDA_INSTRUMENT"]
gran = os.environ["OANDA_GRAN"]
tmp = os.environ["TMP_JSON"]
url = f"{base}/v3/instruments/{inst}/candles?count=500&granularity={gran}&price=M"
request = urllib.request.Request(
    url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = json.loads(response.read())
except Exception as exc:
    sys.stderr.write(f"[OANDA] {type(exc).__name__}\n")
    print("0")
    raise SystemExit(0)

candles = raw.get("candles", [])
if not candles:
    sys.stderr.write("[OANDA] empty\n")
    print("0")
    raise SystemExit(0)

timestamps, opens, highs, lows, closes = [], [], [], [], []
for candle in candles:
    if not candle.get("complete", True):
        continue
    try:
        dt = datetime.datetime.strptime(candle["time"][:19] + "Z", "%Y-%m-%dT%H:%M:%SZ")
        timestamps.append(int(dt.replace(tzinfo=datetime.timezone.utc).timestamp()))
        mid = candle["mid"]
        opens.append(float(mid["o"]))
        highs.append(float(mid["h"]))
        lows.append(float(mid["l"]))
        closes.append(float(mid["c"]))
    except Exception:
        continue

if not timestamps:
    sys.stderr.write("[OANDA] no valid candles\n")
    print("0")
    raise SystemExit(0)

output = {
    "chart": {
        "result": [
            {
                "meta": {"dataGranularity": gran, "_provider": "oanda"},
                "timestamp": timestamps,
                "indicators": {
                    "quote": [
                        {
                            "open": opens,
                            "high": highs,
                            "low": lows,
                            "close": closes,
                        }
                    ]
                },
            }
        ],
        "error": None,
    }
}
json.dump(output, open(tmp, "w", encoding="utf-8"))
print("1")
PY
  )" || OANDA_OK="0"

  if [[ "${OANDA_OK}" = "1" ]]; then
    provider_record oanda success "granularity=${OANDA_GRAN}"
    PROVIDER_USED="oanda"
    log "[FETCH] OANDA OK"
  else
    provider_record oanda failure "granularity=${OANDA_GRAN}"
    log "[FETCH] OANDA FAILED — falling back to Yahoo"
  fi
else
  log "[FETCH] OANDA skipped (token missing or no gran mapping for ${TF})"
fi

if [[ "${PROVIDER_USED}" != "oanda" ]]; then
  Y_SYMBOL="$(yahoo_symbol_for_pair "${PAIR}")"
  Y_INTERVAL="$(yahoo_interval_for_tf "${TF}")"
  Y_RANGE="$(yahoo_range_for_tf "${TF}")"
  [[ -z "${Y_INTERVAL}" ]] && die "no interval mapping for TF='${TF}'"

  URL="https://query1.finance.yahoo.com/v8/finance/chart/${Y_SYMBOL}?range=${Y_RANGE}&interval=${Y_INTERVAL}&includePrePost=false&events=div%7Csplit"
  log "[FETCH] Yahoo fallback: ${Y_SYMBOL} ${Y_INTERVAL} ${Y_RANGE}"

  if command -v curl >/dev/null 2>&1; then
    YAHOO_HTTP="$(
      curl -sSL -A "${UA}" "${URL}" -o "${TMP_JSON}" \
        -w "%{http_code}" --max-time 15 2>>"${LOG_DIR}/error.log" || echo "000"
    )"
    if [[ "${YAHOO_HTTP}" = "429" ]]; then
      provider_record yahoo blocked "http=429"
      log "[FETCH] Yahoo 429 rate-limited — skipping fallback"
      exit 3
    fi
    if [[ "${YAHOO_HTTP}" != "200" || ! -s "${TMP_JSON}" ]]; then
      provider_record yahoo failure "http=${YAHOO_HTTP}"
      die "curl failed (http=${YAHOO_HTTP})"
    fi
  else
    TMP_WGET_HDR="$(mktemp 2>/dev/null || echo "${CACHE_DIR}/.tmp_whdr_${PAIR}_${TF}_$$.txt")"
    wget -qO "${TMP_JSON}" --server-response --timeout=15 \
      --user-agent="${UA}" "${URL}" 2>"${TMP_WGET_HDR}" || true
    if grep -q "HTTP.*429" "${TMP_WGET_HDR}" 2>/dev/null; then
      rm -f "${TMP_WGET_HDR}" 2>/dev/null || true
      provider_record yahoo blocked "http=429"
      log "[FETCH] Yahoo 429 rate-limited — skipping fallback"
      exit 3
    fi
    if [[ ! -s "${TMP_JSON}" ]]; then
      rm -f "${TMP_WGET_HDR}" 2>/dev/null || true
      provider_record yahoo failure "wget_empty_response"
      die "wget failed"
    fi
    rm -f "${TMP_WGET_HDR}" 2>/dev/null || true
  fi

  provider_record yahoo success "interval=${Y_INTERVAL};range=${Y_RANGE}"
  PROVIDER_USED="yahoo"
  log "[FETCH] Yahoo OK"
fi

PY_OUT="$(python3 - "${TMP_JSON}" "${expected_min}" "${PAIR}" "${TF}" "${TMP_CSV}" <<'PY' 2>>"${LOG_DIR}/error.log" || true
import datetime
import json
import math
import statistics
import sys

p_json = sys.argv[1]
expected_min = float(sys.argv[2])
p_csv = sys.argv[5]

def norm_ts(value):
    try:
        if isinstance(value, (int, float)):
            number = int(value)
            number = number // 1000 if number > 100_000_000_000 else number
            return number if number > 0 else None
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        return int(
            datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=datetime.timezone.utc)
            .timestamp()
        )
    except Exception:
        return None

def safe_float(value):
    try:
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    except Exception:
        return None

try:
    data = json.loads(open(p_json, encoding="utf-8").read())
    result = data["chart"]["result"][0]
    granularity = result.get("meta", {}).get("dataGranularity", "")
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    count = min(len(timestamps), len(quote.get("open", [])), len(quote.get("close", [])))
    candles = []
    for index in range(count):
        timestamp = norm_ts(timestamps[index])
        opened = safe_float(quote["open"][index])
        high = safe_float(quote["high"][index])
        low = safe_float(quote["low"][index])
        close = safe_float(quote["close"][index])
        if None not in (timestamp, opened, high, low, close) and close > 0:
            candles.append((timestamp, opened, high, low, close))
    candles.sort()
    normalized = [item[0] for item in candles]
    median = (
        statistics.median(
            [(normalized[index] - normalized[index - 1]) / 60 for index in range(1, len(normalized))]
        )
        if len(normalized) > 1
        else None
    )
    valid = median is not None and abs(median - expected_min) <= max(1.0, expected_min * 0.05)
    if candles:
        with open(p_csv, "w", encoding="utf-8") as handle:
            handle.write("time,open,high,low,close\n")
            for timestamp, opened, high, low, close in candles[-500:]:
                stamp = datetime.datetime.fromtimestamp(
                    timestamp, tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                handle.write(f"{stamp},{opened:.8f},{high:.8f},{low:.8f},{close:.8f}\n")
    print(f"{'0' if valid else '2'} {-1.0 if median is None else float(median)} {granularity}")
except Exception:
    print("1 -1.0")
PY
)"

parts=(${PY_OUT})
rc_gate="${parts[0]:-1}"
med_gate="${parts[1]:--1}"
dg_gate="${parts[2]:-}"

if [[ "${rc_gate}" != "0" ]]; then
  log "[FETCH] FAIL integrity: provider=${PROVIDER_USED} expected=${expected_min} median=${med_gate} granularity=${dg_gate}"
  exit 2
fi

mv -f "${TMP_JSON}" "${OUT_JSON}"
[[ -s "${TMP_CSV}" ]] && mv -f "${TMP_CSV}" "${OUT_CSV}"

if [[ "${TF}" = "${LEGACY_PAIR_CACHE_TF}" ]]; then
  cp -f "${OUT_JSON}" "${LEGACY_JSON}" >/dev/null 2>&1 || true
  log "[FETCH] legacy cache updated: ${LEGACY_JSON}"
else
  log "[FETCH] legacy cache NOT updated (tf=${TF})"
fi

log "[FETCH] OK provider=${PROVIDER_USED} wrote: ${OUT_JSON}"
[[ -f "${OUT_CSV}" ]] && log "[FETCH] OK wrote: ${OUT_CSV}"
exit 0
