#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/data_fetch_candles.sh
# GEM-100 2026-03-09: OANDA primary + Yahoo fallback
###############################################################################
set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${HOME}/BotA"
CACHE_DIR="${ROOT}/cache"
DATA_DIR="${ROOT}/data/candles"
TOOLS_DIR="${ROOT}/tools"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  source "${ROOT}/.env"
  set +a
fi

LEGACY_PAIR_CACHE_TF="${LEGACY_PAIR_CACHE_TF:-H1}"
UA="${UA:-Mozilla/5.0 (Linux; Android 13; Termux) AppleWebKit/537.36}"
OANDA_API_TOKEN="${OANDA_API_TOKEN:-}"
OANDA_API_URL="${OANDA_API_URL:-https://api-fxpractice.oanda.com}"

log() { printf '%s\n' "$*" >&2; }
die() { log "[FETCH] ERROR: $*"; exit 1; }

PAIR_RAW="${1:-}"; TF_RAW="${2:-}"
[[ -z "${PAIR_RAW}" || -z "${TF_RAW}" ]] && { log "Usage: $0 <PAIR> <TF>"; exit 1; }

PAIR="$(printf '%s' "${PAIR_RAW}" | tr -d '/ ' | tr '[:lower:]' '[:upper:]')"
TF="$(printf '%s' "${TF_RAW}" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"

mkdir -p "${CACHE_DIR}" "${DATA_DIR}" "${ROOT}/logs" >/dev/null 2>&1 || true

tf_minutes() {
  local tf="${1:-}"; tf="$(printf '%s' "${tf}" | tr '[:lower:]' '[:upper:]')"
  [[ "${tf}" =~ ^M[0-9]+$ ]] && echo "${tf:1}" && return
  [[ "${tf}" =~ ^H[0-9]+$ ]] && echo "$(( ${tf:1} * 60 ))" && return
  [[ "${tf}" == "D1" || "${tf}" == "1D" ]] && echo "1440" && return
  echo "0"
}

expected_min="$(tf_minutes "${TF}")"
[[ "${expected_min}" -le 0 ]] && die "unsupported TF='${TF}'"

oanda_granularity_for_tf() {
  case "${1:-}" in
    M1) echo "M1";; M5) echo "M5";; M15) echo "M15";; M30) echo "M30";;
    H1) echo "H1";; H2) echo "H2";; H4) echo "H4";; H6) echo "H6";;
    H8) echo "H8";; H12) echo "H12";; D1|1D) echo "D";; *) echo "";;
  esac
}

yahoo_symbol_for_pair() {
  case "${1:-}" in
    EURUSD) echo "EURUSD=X";; GBPUSD) echo "GBPUSD=X";; USDJPY) echo "USDJPY=X";;
    AUDUSD) echo "AUDUSD=X";; USDCAD) echo "USDCAD=X";; USDCHF) echo "USDCHF=X";;
    NZDUSD) echo "NZDUSD=X";; XAUUSD) echo "XAUUSD=X";;
    *) [[ "${#1}" -eq 6 ]] && echo "${1}=X" || echo "${1}";;
  esac
}

yahoo_interval_for_tf() {
  case "${1:-}" in
    M1) echo "1m";; M5) echo "5m";; M15) echo "15m";; M30) echo "30m";;
    H1) echo "1h";; H4) echo "4h";; D1|1D) echo "1d";; *) echo "";;
  esac
}

yahoo_range_for_tf() {
  case "${1:-}" in
    M1|M2|M5) echo "1d";; M15|M30) echo "5d";;
    H1|H2|H4) echo "5d";; D1|1D) echo "1mo";; *) echo "2d";;
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

# ── PRIMARY: OANDA ────────────────────────────────────────────────────────────
OANDA_GRAN="$(oanda_granularity_for_tf "${TF}")"
OANDA_INSTRUMENT="${PAIR:0:3}_${PAIR:3:3}"

if [[ -n "${OANDA_API_TOKEN}" && -n "${OANDA_GRAN}" ]]; then
  log "[FETCH] trying OANDA: instrument=${OANDA_INSTRUMENT} gran=${OANDA_GRAN}"
  OANDA_OK="$(
  OANDA_API_TOKEN="${OANDA_API_TOKEN}" OANDA_API_URL="${OANDA_API_URL}" \
  OANDA_INSTRUMENT="${OANDA_INSTRUMENT}" OANDA_GRAN="${OANDA_GRAN}" \
  TMP_JSON="${TMP_JSON}" python3 << 'PY' 2>>"${ROOT}/logs/error.log"
import os, json, urllib.request, datetime, sys

token=os.environ["OANDA_API_TOKEN"]; base=os.environ["OANDA_API_URL"].rstrip("/")
inst=os.environ["OANDA_INSTRUMENT"]; gran=os.environ["OANDA_GRAN"]
tmp=os.environ["TMP_JSON"]

url=f"{base}/v3/instruments/{inst}/candles?count=500&granularity={gran}&price=M"
req=urllib.request.Request(url,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
try:
  with urllib.request.urlopen(req,timeout=15) as r: raw=json.loads(r.read())
except Exception as e:
  sys.stderr.write(f"[OANDA] {type(e).__name__}\n"); print("0"); sys.exit(0)

candles=raw.get("candles",[])
if not candles: sys.stderr.write("[OANDA] empty\n"); print("0"); sys.exit(0)

ts,opens,highs,lows,closes=[],[],[],[],[]
for c in candles:
  if not c.get("complete",True): continue
  try:
    dt=datetime.datetime.strptime(c["time"][:19]+"Z","%Y-%m-%dT%H:%M:%SZ")
    ts.append(int(dt.replace(tzinfo=datetime.timezone.utc).timestamp()))
    m=c["mid"]; opens.append(float(m["o"])); highs.append(float(m["h"]))
    lows.append(float(m["l"])); closes.append(float(m["c"]))
  except: continue

if not ts: sys.stderr.write("[OANDA] no valid candles\n"); print("0"); sys.exit(0)

out={"chart":{"result":[{"meta":{"dataGranularity":gran,"_provider":"oanda"},
  "timestamp":ts,"indicators":{"quote":[{"open":opens,"high":highs,"low":lows,"close":closes}]}}],"error":None}}
json.dump(out,open(tmp,"w")); print("1")
PY
  )" || OANDA_OK="0"

  if [[ "${OANDA_OK}" == "1" ]]; then
    PROVIDER_USED="oanda"
    log "[FETCH] OANDA OK"
  else
    log "[FETCH] OANDA FAILED — falling back to Yahoo"
  fi
else
  log "[FETCH] OANDA skipped (token missing or no gran mapping for ${TF})"
fi

# ── FALLBACK: Yahoo ───────────────────────────────────────────────────────────
if [[ "${PROVIDER_USED}" != "oanda" ]]; then
  Y_SYMBOL="$(yahoo_symbol_for_pair "${PAIR}")"
  Y_INTERVAL="$(yahoo_interval_for_tf "${TF}")"
  Y_RANGE="$(yahoo_range_for_tf "${TF}")"
  [[ -z "${Y_INTERVAL}" ]] && die "no interval mapping for TF='${TF}'"

  URL="https://query1.finance.yahoo.com/v8/finance/chart/${Y_SYMBOL}?range=${Y_RANGE}&interval=${Y_INTERVAL}&includePrePost=false&events=div%7Csplit"
  log "[FETCH] Yahoo fallback: ${Y_SYMBOL} ${Y_INTERVAL} ${Y_RANGE}"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -A "${UA}" "${URL}" -o "${TMP_JSON}" 2>>"${ROOT}/logs/error.log" || die "curl failed"
  else
    wget -qO "${TMP_JSON}" --user-agent="${UA}" "${URL}" 2>>"${ROOT}/logs/error.log" || die "wget failed"
  fi
  [[ -s "${TMP_JSON}" ]] || die "empty response (Yahoo)"
  PROVIDER_USED="yahoo"
  log "[FETCH] Yahoo OK"
fi

# ── Integrity gate ────────────────────────────────────────────────────────────
PY_OUT="$(python3 - << 'PY' "${TMP_JSON}" "${expected_min}" "${PAIR}" "${TF}" "${TMP_CSV}" 2>>"${ROOT}/logs/error.log" || true
import json,sys,statistics,datetime,math
p_json=sys.argv[1]; expected_min=float(sys.argv[2]); p_csv=sys.argv[5]

def norm_ts(t):
  try:
    if isinstance(t,(int,float)):
      v=int(t); v=v//1000 if v>100_000_000_000 else v; return v if v>0 else None
    s=str(t).strip()
    if s.isdigit(): return int(s)
    return int(datetime.datetime.strptime(s,"%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp())
  except: return None

def sf(x):
  try: v=float(x); return None if (math.isnan(v) or math.isinf(v)) else v
  except: return None

try:
  d=json.loads(open(p_json).read())
  r=d["chart"]["result"][0]; dg=r.get("meta",{}).get("dataGranularity","")
  ts=r.get("timestamp",[]); q=r.get("indicators",{}).get("quote",[{}])[0]
  n=min(len(ts),len(q.get("open",[])),len(q.get("close",[])))
  candles=[]
  for i in range(n):
    t=norm_ts(ts[i]); o=sf(q["open"][i]); h=sf(q["high"][i]); l=sf(q["low"][i]); c=sf(q["close"][i])
    if None not in (t,o,h,l,c) and c>0: candles.append((t,o,h,l,c))
  candles.sort()
  ts2=[x[0] for x in candles]
  med=statistics.median([(ts2[i]-ts2[i-1])/60 for i in range(1,len(ts2))]) if len(ts2)>1 else None
  ok=med is not None and abs(med-expected_min)<=max(1.0,expected_min*0.05)
  if candles:
    with open(p_csv,"w") as f:
      f.write("time,open,high,low,close\n")
      for t,o,h,l,c in candles[-500:]:
        dt=datetime.datetime.fromtimestamp(t,tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{dt},{o:.8f},{h:.8f},{l:.8f},{c:.8f}\n")
  print(f"{'0' if ok else '2'} {-1.0 if med is None else float(med)} {dg}")
except: print("1 -1.0")
PY
)"

parts=(${PY_OUT})
rc_gate="${parts[0]:-1}"; med_gate="${parts[1]:--1}"; dg_gate="${parts[2]:-}"

if [[ "${rc_gate}" != "0" ]]; then
  log "[FETCH] FAIL integrity: provider=${PROVIDER_USED} expected=${expected_min} median=${med_gate}"
  exit 2
fi

mv -f "${TMP_JSON}" "${OUT_JSON}"
[[ -s "${TMP_CSV}" ]] && mv -f "${TMP_CSV}" "${OUT_CSV}"

if [[ "${TF}" == "${LEGACY_PAIR_CACHE_TF}" ]]; then
  cp -f "${OUT_JSON}" "${LEGACY_JSON}" >/dev/null 2>&1 || true
  log "[FETCH] legacy cache updated: ${LEGACY_JSON}"
else
  log "[FETCH] legacy cache NOT updated (tf=${TF})"
fi

log "[FETCH] OK provider=${PROVIDER_USED} wrote: ${OUT_JSON}"
[[ -f "${OUT_CSV}" ]] && log "[FETCH] OK wrote: ${OUT_CSV}"
exit 0
