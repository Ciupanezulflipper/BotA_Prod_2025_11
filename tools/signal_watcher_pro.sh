#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/signal_watcher_pro.sh
# VERSION: v2.0.2 — 2026-02-21 candle-timestamp staleness (weekend-safe)
#
# ROLE:
#   Watcher/orchestrator for BotA. Runs fusion, logs decisions, writes alerts.csv,
#   and optionally sends Telegram alerts.
#
# KEY FIX (Audit Gemini + DeepSeek):
#   - Staleness is based on *market reality* (last candle timestamp inside raw cache JSON),
#     NOT on file mtime of indicators_*.json (which can be “zombie fresh” on weekends).
#
# AUTHORITATIVE INPUTS (per tools/PRD.md + S28 proof):
#   - Candle cache:      cache/<PAIR>_<TF>.json   (Yahoo "chart" payload)
#   - Indicators cache:  cache/indicators_<PAIR>_<TF>.json
#   - Legacy cache/<PAIR>.json may exist; NEVER used for TF-specific freshness.
#
# STALE BEHAVIOR (fail-closed):
#   - If candle timestamp missing/unparseable OR raw cache missing => SKIP.
#   - If candle age > CANDLE_MAX_AGE_SECS => SKIP.
#
# OPTIONAL:
#   - Indicators mtime age can be logged as non-blocking lag warning.
#
# TIERED ROUTING (Telegram):
#   score >= TELEGRAM_TIER_GREEN_MIN  => 🟢 full alert (entry/SL/TP)
#   score >= TELEGRAM_TIER_YELLOW_MIN => 🟡 watchlist (no entry/SL/TP)
#   score <  TELEGRAM_TIER_YELLOW_MIN => silent (CSV only on NEW signals)
###############################################################################

set -euo pipefail
set +x
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="${ROOT}/tools"

ts_iso() { date +"%Y-%m-%dT%H:%M:%S%z"; }

log() {
  local tag="${1:-WATCHER}"
  shift || true
  printf '[%s %s] %s\n' "${tag}" "$(ts_iso)" "$*" >&2
}

abs_under_root() {
  local p="${1:-}"
  if [[ -z "${p}" ]]; then
    echo "${ROOT}"
    return 0
  fi
  if [[ "${p}" == /* ]]; then
    echo "${p}"
  else
    echo "${ROOT}/${p}"
  fi
}

is_true() {
  local v="${1:-}"
  v="${v,,}"
  case "${v}" in
    1|true|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_false() {
  local v="${1:-}"
  v="${v,,}"
  case "${v}" in
    0|false|no|n|off|"") return 0 ;;
    *) return 1 ;;
  esac
}

# Safe KEY=VALUE loader that EXPORTS variables for Python.
# Does NOT override variables already present in the process environment.
env_safe_source_no_override() {
  local f="${1:-}"
  [[ -f "${f}" ]] || return 0

  local line key val
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "${line}" ]] && continue
    [[ "${line}" == \#* ]] && continue

    if [[ "${line}" == export\ * ]]; then
      line="${line#export }"
      line="${line#"${line%%[![:space:]]*}"}"
    fi

    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"

      # If already present in environment (including empty), do not override.
      if printenv "${key}" >/dev/null 2>&1; then
        continue
      fi

      # Strip surrounding quotes if present
      if [[ "${val}" =~ ^\"(.*)\"$ ]]; then
        val="${BASH_REMATCH[1]}"
      elif [[ "${val}" =~ ^\'(.*)\'$ ]]; then
        val="${BASH_REMATCH[1]}"
      fi

      export "${key}=${val}"
    fi
  done < "${f}"
}

load_env_startup() {
  env_safe_source_no_override "${ROOT}/.env"
  env_safe_source_no_override "${ROOT}/config/strategy.env"

  : "${PAIRS:=EURUSD GBPUSD}"
  : "${TIMEFRAMES:=M15}"
  : "${SLEEP_SECONDS:=300}"

  : "${DRY_RUN_MODE:=false}"
  : "${TELEGRAM_ENABLED:=1}"
  : "${TELEGRAM_MIN_SCORE:=0}"     # legacy extra gate; keep 0 to disable
  : "${FILTER_SCORE_MIN:=0}"
  : "${TELEGRAM_COOLDOWN_SECONDS:=300}"

  : "${LOGS:=logs}"
  : "${CACHE:=cache}"
  : "${STATE:=logs/state}"
  : "${ALERTS_CSV:=logs/alerts.csv}"
  : "${ERRLOG:=logs/error.log}"

  # Back-compat: historically this value gated "indicator mtime age".
  # Now it gates *candle age* (market reality). Keep the name for existing envs.
  : "${INDICATOR_MAX_AGE_SECS:=1200}"     # default 20 min
  : "${CANDLE_MAX_AGE_SECS:=${INDICATOR_MAX_AGE_SECS}}"

  # Non-blocking indicator lag warning (optional).
  : "${INDICATOR_LAG_WARN_SECS:=900}"     # default 15 min; set 0 to disable warnings

  # Network failure backoff threshold
  : "${NETWORK_FAIL_MAX:=3}"

  LOGS="$(abs_under_root "${LOGS}")"
  CACHE="$(abs_under_root "${CACHE}")"
  STATE="$(abs_under_root "${STATE}")"
  ALERTS_CSV="$(abs_under_root "${ALERTS_CSV}")"
  ERRLOG="$(abs_under_root "${ERRLOG}")"

  mkdir -p "${LOGS}" "${CACHE}" "${STATE}"
  touch "${ERRLOG}" 2>/dev/null || true

  # Backward compatibility: FILTER_SCORE_MIN → FILTER_SCORE_MIN_ALL mapping.
  if [[ -n "${FILTER_SCORE_MIN:-}" && -z "${FILTER_SCORE_MIN_ALL:-}" ]]; then
    export FILTER_SCORE_MIN_ALL="${FILTER_SCORE_MIN}"
    export _BOTA_MAPPED_FILTER_SCORE_MIN_ALL="1"
  fi

  # Resolve TELEGRAM_BOT_TOKEN from TELEGRAM_TOKEN if not already set.
  : "${TELEGRAM_BOT_TOKEN:=${TELEGRAM_TOKEN:-}}"
  export TELEGRAM_BOT_TOKEN

  # Tiered routing thresholds (Telegram-side).
  : "${TELEGRAM_TIER_GREEN_MIN:=75}"

  # If not explicitly set, derive yellow threshold from active filter threshold.
  if [[ -z "${TELEGRAM_TIER_YELLOW_MIN:-}" ]]; then
    if [[ -n "${FILTER_SCORE_MIN_ALL:-}" ]]; then
      TELEGRAM_TIER_YELLOW_MIN="${FILTER_SCORE_MIN_ALL}"
    else
      TELEGRAM_TIER_YELLOW_MIN="60"
    fi
    export TELEGRAM_TIER_YELLOW_MIN
  fi

  # Precompute integer thresholds safely (floor).
  TELEGRAM_TIER_GREEN_MIN_INT="$(VAL="${TELEGRAM_TIER_GREEN_MIN}" python3 -c "
import os, math
try:
    s=float(os.environ.get('VAL','0'))
    print(int(math.floor(s + 1e-9)))
except Exception:
    print(0)
" 2>/dev/null || echo 0)"

  TELEGRAM_TIER_YELLOW_MIN_INT="$(VAL="${TELEGRAM_TIER_YELLOW_MIN}" python3 -c "
import os, math
try:
    s=float(os.environ.get('VAL','0'))
    print(int(math.floor(s + 1e-9)))
except Exception:
    print(0)
" 2>/dev/null || echo 0)"

  export TELEGRAM_TIER_GREEN_MIN_INT TELEGRAM_TIER_YELLOW_MIN_INT

  NETWORK_FAIL_FILE="${STATE}/network_fail_count.txt"
  export NETWORK_FAIL_FILE
}

usage() {
  cat <<'USAGE'
Usage:
  bash tools/signal_watcher_pro.sh --once
  bash tools/signal_watcher_pro.sh

Env precedence: CLI > .env > config/strategy.env

Key env:
  PAIRS="EURUSD GBPUSD ..."
  TIMEFRAMES="M15 H1 ..."
  DRY_RUN_MODE=true|false|1|0
  TELEGRAM_ENABLED=0|1
  TELEGRAM_CHAT_ID=...
  TELEGRAM_BOT_TOKEN=...  (or TELEGRAM_TOKEN; auto-mapped)
  FILTER_SCORE_MIN_ALL=NN
  TELEGRAM_COOLDOWN_SECONDS=NN

Staleness (market reality):
  CANDLE_MAX_AGE_SECS=NN         (default: INDICATOR_MAX_AGE_SECS, back-compat)
  INDICATOR_MAX_AGE_SECS=NN      (back-compat alias for CANDLE_MAX_AGE_SECS)

Optional non-blocking lag warning:
  INDICATOR_LAG_WARN_SECS=NN     (0 disables)

Tier routing:
  TELEGRAM_TIER_GREEN_MIN=75
  TELEGRAM_TIER_YELLOW_MIN=auto (defaults to FILTER_SCORE_MIN_ALL else 60)
USAGE
}

ensure_alerts_csv() {
  if [[ ! -f "${ALERTS_CSV}" || ! -s "${ALERTS_CSV}" ]]; then
    printf '%s\n' "ts,pair,tf,direction,score,confidence,entry,sl,tp,provider,filter_rejected,filter_reasons,reasons,ema_comp,rsi_comp,macd_comp,adx_comp,adx_raw,rsi_raw,macd_hist_raw,macro6,h1_trend,tier,session,adx_regime" > "${ALERTS_CSV}"
  fi
}

append_alert_csv() {
  local ts="$1" pair="$2" tf="$3" direction="$4" score="$5" conf="$6"
  local entry="$7" sl="$8" tp="$9" provider="${10}"
  local filter_rejected="${11}" filter_reasons="${12}" reasons="${13}"
  local ema_comp="${14:-}" rsi_comp="${15:-}" macd_comp="${16:-}" adx_comp="${17:-}"
  local adx_raw="${18:-}" rsi_raw="${19:-}" macd_hist_raw="${20:-}"
  local macro6="${21:-}" h1_trend="${22:-}" tier="${23:-}" session="${24:-}" adx_regime="${25:-}"

  TS="${ts}" PAIR="${pair}" TF="${tf}" DIRECTION="${direction}" SCORE="${score}" CONF="${conf}" \
  ENTRY="${entry}" SL="${sl}" TP="${tp}" PROVIDER="${provider}" REJ="${filter_rejected}" \
  FRS="${filter_reasons}" RSN="${reasons}" CSV_PATH="${ALERTS_CSV}" \
  EMA_COMP="${ema_comp}" RSI_COMP="${rsi_comp}" MACD_COMP="${macd_comp}" ADX_COMP="${adx_comp}" \
  ADX_RAW="${adx_raw}" RSI_RAW="${rsi_raw}" MACD_HIST_RAW="${macd_hist_raw}" \
  MACRO6="${macro6}" H1_TREND="${h1_trend}" TIER="${tier}" SESSION="${session}" ADX_REGIME="${adx_regime}" \
  python3 -c '
import os, csv, re
from datetime import datetime, timezone

def get(k, d=""): return os.environ.get(k, d)

# Parse component values from reasons string (e.g. "ema_comp=2.6|rsi_comp=6.5|...")
reasons = get("RSN","")
def parse_reason(key):
    m = re.search(rf"{key}=([\d.\-]+)", reasons)
    return m.group(1) if m else get(key.upper().replace("_","_"), "")

# Session detection from UTC hour
try:
    hour = datetime.now(timezone.utc).hour
    if 7 <= hour < 9:   session = "London_open"
    elif 9 <= hour < 12: session = "London"
    elif 12 <= hour < 13: session = "London_NY_overlap"
    elif 13 <= hour < 17: session = "NY"
    elif 17 <= hour < 21: session = "NY_close"
    else: session = "Asian"
except Exception:
    session = get("SESSION","")

# ADX regime
try:
    adx_val = float(parse_reason("adx") or get("ADX_RAW","0") or 0)
    adx_regime = "trending" if adx_val >= 20.0 else "ranging"
except Exception:
    adx_regime = get("ADX_REGIME","")

row = [
  get("TS"), get("PAIR"), get("TF"), get("DIRECTION"),
  get("SCORE"), get("CONF"), get("ENTRY"), get("SL"), get("TP"),
  get("PROVIDER"), get("REJ"), get("FRS"), get("RSN"),
  parse_reason("ema_comp"), parse_reason("rsi_comp"),
  parse_reason("macd_comp"), parse_reason("adx_comp"),
  parse_reason("adx"), parse_reason("rsi"), parse_reason("macd_hist"),
  get("MACRO6"), get("H1_TREND"), get("TIER"), session, adx_regime,
]
path = get("CSV_PATH","alerts.csv")
with open(path, "a", newline="", encoding="utf-8") as f:
  csv.writer(f).writerow(row)
' 2>/dev/null || true
}

payload_is_blank() {
  local s="${1:-}"
  [[ -z "$(printf '%s' "${s}" | tr -d ' \t\r\n')" ]]
}

# Content-based signal dedup.
# Returns 0 if NEW, 1 if DUPLICATE.
signal_is_new() {
  local pair="$1" tf="$2" direction="$3" score="$4" entry="$5" sl="$6" tp="$7"
  local hash_input="${pair}|${tf}|${direction}|${score}|${entry}|${sl}|${tp}"
  local sig_hash hash_file old_hash

  sig_hash="$(printf '%s' "${hash_input}" | md5sum 2>/dev/null | cut -d' ' -f1 || printf '%s' "${hash_input}" | cksum | cut -d' ' -f1)"
  hash_file="${STATE}/last_hash_${pair}_${tf}.txt"

  if [[ -f "${hash_file}" ]]; then
    old_hash="$(cat "${hash_file}" 2>/dev/null || echo "")"
    if [[ "${old_hash}" == "${sig_hash}" ]]; then
      return 1
    fi
  fi

  printf '%s' "${sig_hash}" > "${hash_file}" 2>/dev/null || true
  return 0
}

raw_cache_path() {
  local pair="$1" tf="$2"
  echo "${CACHE}/${pair}_${tf}.json"
}

# Candle-based staleness (authoritative).
# Output TSV: "<age_secs|missing>\t<last_utc>\t<source>"
candle_age_info() {
  local pair="$1" tf="$2"
  local raw_file
  raw_file="$(raw_cache_path "${pair}" "${tf}")"

  if [[ ! -f "${raw_file}" ]]; then
    printf 'missing\t\traw_missing\n'
    return 0
  fi

  RAW_PATH="${raw_file}" python3 - <<'PY' 2>/dev/null || printf 'missing\t\tpython_error\n'
import os, json
from datetime import datetime, timezone

path = os.environ.get("RAW_PATH","")
def out(age, last, src):
  print(f"{age}\t{last}\t{src}")

try:
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
except Exception:
  out("missing", "", "json_parse_error")
  raise SystemExit(0)

now = datetime.now(timezone.utc)

# Case A: explicit ISO timestamp if present
if isinstance(data, dict):
  ts = data.get("last_candle_utc")
  if isinstance(ts, str) and ts.strip():
    s = ts.strip()
    try:
      if s.endswith("Z"):
        s = s[:-1] + "+00:00"
      dt = datetime.fromisoformat(s)
      if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
      age = int((now - dt).total_seconds())
      if age < 0:
        out("missing", "", "future_ts")
      else:
        out(str(age), dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "last_candle_utc")
      raise SystemExit(0)
    except Exception:
      out("missing", "", "last_candle_utc_parse_error")
      raise SystemExit(0)

# Case B: Yahoo chart payload: chart.result[0].timestamp[-1]
try:
  chart = data.get("chart") if isinstance(data, dict) else None
  if not isinstance(chart, dict):
    out("missing", "", "no_chart_key")
    raise SystemExit(0)

  result = chart.get("result") or []
  r0 = result[0] if isinstance(result, list) and result and isinstance(result[0], dict) else {}
  ts_list = r0.get("timestamp") or []
  if not (isinstance(ts_list, list) and ts_list):
    out("missing", "", "no_timestamp_list")
    raise SystemExit(0)

  last_epoch = int(ts_list[-1])
  dt = datetime.fromtimestamp(last_epoch, tz=timezone.utc)
  age = int((now - dt).total_seconds())
  if age < 0:
    out("missing", "", "future_epoch")
  else:
    out(str(age), dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "chart_timestamp")
except Exception:
  out("missing", "", "chart_extract_error")
PY
}

# Non-authoritative: indicator file mtime (use only as lag warning).
indicators_mtime_age_secs() {
  local pair="$1" tf="$2"
  local ind_file="${CACHE}/indicators_${pair}_${tf}.json"

  if [[ ! -f "${ind_file}" ]]; then
    echo "missing"
    return 0
  fi

  local file_mtime now_epoch age_secs
  file_mtime="$(stat -c %Y "${ind_file}" 2>/dev/null || echo 0)"
  now_epoch="$(date +%s)"
  age_secs=$(( now_epoch - file_mtime ))
  echo "${age_secs}"
  return 0
}

# Back-compat alias (older code referenced indicators_age_secs).
indicators_age_secs() { indicators_mtime_age_secs "$@"; }

run_fusion() {
  local pair="$1"
  local tf="$2"

  # Pass both pair AND tf to fusion script.
  if [[ -x "${TOOLS}/m15_h1_fusion.sh" ]]; then
    bash "${TOOLS}/m15_h1_fusion.sh" "${pair}" "${tf}" 2>>"${ERRLOG}" || true
    return 0
  fi

  # Fallback: scoring_engine + quality_filter if available
  if [[ -x "${TOOLS}/scoring_engine.sh" && -f "${TOOLS}/quality_filter.py" ]]; then
    local raw
    raw="$(bash "${TOOLS}/scoring_engine.sh" "${pair}" "${tf}" 2>>"${ERRLOG}" || true)"
    if [[ -n "${raw}" ]]; then
      printf '%s' "${raw}" | python3 "${TOOLS}/quality_filter.py" 2>>"${ERRLOG}" || true
      return 0
    fi
  fi

  PAIR="${pair}" TF="${tf}" python3 -c '
import os, json
pair=os.environ.get("PAIR","UNKNOWN")
tf=os.environ.get("TF","UNKNOWN")
print(json.dumps({
  "pair":pair,"tf":tf,"direction":"HOLD",
  "entry":0.0,"sl":0.0,"tp":0.0,"volatility":"unknown",
  "score":0.0,"confidence":40.0,
  "reasons":"fusion_unavailable",
  "price":0.0,"provider":"watcher_fallback",
  "atr":0.0,"filter_rr":0.0,"filter_atr":0.0,
  "filter_rejected":True,"filter_reasons":["fail_closed","fusion_unavailable"],
  "pattern_delta":0
}, separators=(",",":")))
'
}

parse_payload_tsv() {
  python3 /dev/fd/3 3<<'PY'
import sys, json

def sf(v, d=0.0):
  try:
    return float(v)
  except Exception:
    return d

raw = sys.stdin.read()
dec = json.JSONDecoder()

data = None
parse_ok = False

s = raw
i = 0
last_dict = None

while True:
  j = s.find("{", i)
  if j == -1:
    break
  try:
    obj, end = dec.raw_decode(s, j)
    i = end
    if isinstance(obj, dict):
      last_dict = obj
    elif isinstance(obj, list) and obj and isinstance(obj[-1], dict):
      last_dict = obj[-1]
    continue
  except Exception:
    i = j + 1
    continue

if isinstance(last_dict, dict):
  data = last_dict
  parse_ok = True
else:
  data = {}
  parse_ok = False

pair = str(data.get("pair") or "").strip()
tf = str(data.get("tf", data.get("timeframe","")) or "").strip()
direction = str(data.get("direction","HOLD")).upper()

score = sf(data.get("score",0.0),0.0)
conf = sf(data.get("confidence",0.0),0.0)
entry = sf(data.get("entry",0.0),0.0)
sl = sf(data.get("sl",0.0),0.0)
tp = sf(data.get("tp",0.0),0.0)

provider = str(data.get("provider","engine_A2"))
rejected = bool(data.get("filter_rejected", False))

fr = data.get("filter_reasons", [])
if isinstance(fr, list):
  filter_str = " | ".join(str(x) for x in fr)
else:
  filter_str = str(fr) if fr is not None else ""

reasons = str(data.get("reasons",""))

if not parse_ok:
  rejected = True
  if not filter_str:
    filter_str = "parse_error"
  if not reasons:
    reasons = "parse_error"

if not pair:
  pair = "UNKNOWN"
  rejected = True
  filter_str = (filter_str + " | empty_pair").strip(" |") if filter_str else "empty_pair"

if not tf:
  tf = "UNKNOWN"
  rejected = True
  filter_str = (filter_str + " | empty_tf").strip(" |") if filter_str else "empty_tf"

def clean(s):
  return s.replace("\t", " ").replace("\n", " ").replace("\r", "")

out = [
  clean(pair),
  clean(tf),
  clean(direction),
  f"{score:.2f}",
  f"{conf:.2f}",
  f"{entry:.5f}",
  f"{sl:.5f}",
  f"{tp:.5f}",
  clean(provider),
  "true" if rejected else "false",
  clean(filter_str),
  clean(reasons),
]

sys.stdout.write("\t".join(out))
PY
}

telegram_cooldown_check() {
  local pair="$1" tf="$2"
  local cooldown="${TELEGRAM_COOLDOWN_SECONDS:-300}"
  local key="${STATE}/last_sent_${pair}_${tf}.txt"
  local now last
  now="$(date +%s)"
  last="0"
  if [[ -f "${key}" ]]; then
    last="$(cat "${key}" 2>/dev/null || echo 0)"
  fi
  if [[ "${last}" =~ ^[0-9]+$ ]] && (( now - last < cooldown )); then
    return 1
  fi
  return 0
}

telegram_cooldown_mark() {
  local pair="$1" tf="$2"
  local key="${STATE}/last_sent_${pair}_${tf}.txt"
  date +%s > "${key}" 2>/dev/null || true
}

network_fail_count() {
  if [[ -f "${NETWORK_FAIL_FILE}" ]]; then
    cat "${NETWORK_FAIL_FILE}" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

network_fail_increment() {
  local count
  count="$(network_fail_count)"
  if [[ "${count}" =~ ^[0-9]+$ ]]; then
    echo $(( count + 1 )) > "${NETWORK_FAIL_FILE}" 2>/dev/null || true
  else
    echo 1 > "${NETWORK_FAIL_FILE}" 2>/dev/null || true
  fi
}

network_fail_reset() {
  echo 0 > "${NETWORK_FAIL_FILE}" 2>/dev/null || true
}

can_send_telegram() {
  is_false "${TELEGRAM_ENABLED:-1}" && return 1
  is_true "${DRY_RUN_MODE:-false}" && return 1
  [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] || return 1
  [[ -n "${TELEGRAM_CHAT_ID:-}" ]] || return 1
  return 0
}

# Returns 0 on success, 1 on failure.
send_telegram_message() {
  local msg="$1"

  # Dry run or disabled => log and return success, but caller must NOT mark cooldown.
  if is_true "${DRY_RUN_MODE:-false}" || is_false "${TELEGRAM_ENABLED:-1}"; then
    log "TELEGRAM" "DRY_RUN or disabled: would send: ${msg}"
    return 0
  fi

  if ! can_send_telegram; then
    log "TELEGRAM" "FAILED: missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or disabled"
    return 1
  fi

  local fail_count
  fail_count="$(network_fail_count)"
  if [[ "${fail_count}" =~ ^[0-9]+$ ]] && (( fail_count >= NETWORK_FAIL_MAX )); then
    log "TELEGRAM" "backoff: ${fail_count} consecutive network failures (max=${NETWORK_FAIL_MAX}), skipping send"
    return 1
  fi

  if [[ -x "${TOOLS}/telegram_send.sh" ]]; then
    if "${TOOLS}/telegram_send.sh" "${msg}" 2>>"${ERRLOG}"; then
      log "TELEGRAM" "SENT: via tools/telegram_send.sh"
      network_fail_reset
      return 0
    else
      log "TELEGRAM" "FAILED: tools/telegram_send.sh error"
      network_fail_increment
      return 1
    fi
  fi

  # Python urllib send (token never printed; errors are sanitized to type only)
  if TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}" MSG="${msg}" \
    python3 -c '
import os, sys, urllib.parse, urllib.request

token = os.environ.get("TELEGRAM_BOT_TOKEN","")
chat_id = os.environ.get("TELEGRAM_CHAT_ID","")
msg = os.environ.get("MSG","")

if not token or not chat_id:
  sys.stderr.write("[TELEGRAM] missing token/chat_id\n")
  sys.exit(1)

url = f"https://api.telegram.org/bot{token}/sendMessage"
msg = msg.replace("\\n", "\n")
data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode("utf-8")
req = urllib.request.Request(url, data=data, method="POST")

try:
  with urllib.request.urlopen(req, timeout=15) as r:
    r.read()
  sys.exit(0)
except Exception as e:
  # SECURITY: do NOT print str(e) (may include URL). Print type only.
  sys.stderr.write(f"[TELEGRAM] send failed: {type(e).__name__}\n")
  sys.exit(1)
' 2>>"${ERRLOG}"; then
    log "TELEGRAM" "SENT: via python urllib"
    network_fail_reset
    return 0
  else
    log "TELEGRAM" "FAILED: python urllib error"
    network_fail_increment
    return 1
  fi
}

process_pair_tf() {
  local pair="$1"
  local tf="$2"

  # AUTHORITATIVE staleness guard BEFORE fusion: last candle timestamp in cache/<PAIR>_<TF>.json
  local age_tsv age last_utc src
  age_tsv="$(candle_age_info "${pair}" "${tf}" || true)"
  IFS=$'\t' read -r age last_utc src <<< "${age_tsv}"

  if [[ "${age}" == "missing" ]]; then
    log "STALE" "${pair} ${tf} raw_cache missing/invalid (src=${src}) file=$(raw_cache_path "${pair}" "${tf}") -> SKIP"
    return 0
  fi

  if [[ "${age}" =~ ^[0-9]+$ ]] && (( age > CANDLE_MAX_AGE_SECS )); then
    log "STALE" "${pair} ${tf} candle_stale age=${age}s max=${CANDLE_MAX_AGE_SECS}s last=${last_utc} src=${src} -> SKIP"
    return 0
  fi

  # I-10 FIX: Pause guard — skip pair if daily -3R circuit breaker triggered
  local pause_file="${HOME}/BotA/state/pause"
  if [[ -f "${pause_file}" ]]; then
    local pause_key="PAUSE_${pair}"
    if grep -q "export ${pause_key}=1" "${pause_file}" 2>/dev/null; then
      log "PAUSE" "${pair} ${tf} skipped — daily -3R circuit breaker active"
      return 0
    fi
  fi

  # I-11 FIX: News gate — block 60min around NFP/CPI/FOMC via news_filter_real.py
  local news_ok
  news_ok="$(python3 -c "
import sys; sys.path.insert(0,'${TOOLS}')
from news_filter_real import news_risk_gate
ok, note = news_risk_gate('${pair}')
print('1' if ok else '0')
print(note)
" 2>/dev/null || echo "1")"
  local news_ok_flag note_line
  news_ok_flag="$(echo "$news_ok" | head -1)"
  note_line="$(echo "$news_ok" | tail -1)"
  if [[ "${news_ok_flag}" == "0" ]]; then
    log "NEWS_GATE" "${pair} ${tf} blocked — ${note_line}"
    return 0
  fi

  # Calendar guard — DISABLED (RapidAPI free tier too limited, re-enable with paid plan)
  if [[ "${CALENDAR_GUARD_ENABLED:-0}" == "1" ]]; then
    if ! RAPIDAPI_CALENDAR_KEY="${RAPIDAPI_CALENDAR_KEY}"          python3 "${TOOLS}/calendar_guard.py" --pair "${pair}" 2>/dev/null; then
      log "CALENDAR_BLOCK" "${pair} ${tf} blocked by news event"
      return 0
    fi
  fi

  # Optional lag warning: indicators file mtime age (non-blocking).
  if [[ "${INDICATOR_LAG_WARN_SECS:-0}" =~ ^[0-9]+$ ]] && (( INDICATOR_LAG_WARN_SECS > 0 )); then
    local ind_age
    ind_age="$(indicators_mtime_age_secs "${pair}" "${tf}" || true)"
    if [[ "${ind_age}" =~ ^[0-9]+$ ]] && (( ind_age > INDICATOR_LAG_WARN_SECS )); then
      log "LAG" "${pair} ${tf} indicators_mtime_age=${ind_age}s warn=${INDICATOR_LAG_WARN_SECS}s (non-blocking)"
    fi
  fi

  local payload
  payload="$(run_fusion "${pair}" "${tf}" || true)"

  if payload_is_blank "${payload}"; then
    payload=""
  fi

  if [[ -z "${payload}" ]]; then
    log "DEBUG" "${pair} ${tf} fusion_stdout_empty -> using fail_closed fallback JSON"
    payload="$(PAIR="${pair}" TF="${tf}" python3 -c '
import os, json
print(json.dumps({
  "pair":os.environ.get("PAIR","UNKNOWN"),
  "tf":os.environ.get("TF","UNKNOWN"),
  "direction":"HOLD",
  "entry":0.0,"sl":0.0,"tp":0.0,"volatility":"unknown",
  "score":0.0,"confidence":40.0,
  "reasons":"empty_payload",
  "price":0.0,"provider":"watcher_empty",
  "atr":0.0,"filter_rr":0.0,"filter_atr":0.0,
  "filter_rejected":True,"filter_reasons":["fail_closed","empty_payload"],
  "pattern_delta":0
}, separators=(",",":")))
')"
  fi

  local tsv
  tsv="$(printf '%s' "${payload}" | parse_payload_tsv || true)"
  if [[ -z "${tsv}" ]]; then
    log "FILTER" "${pair} ${tf} rejected_by_filter score=0.0 conf=40.0 filters=parse_error(tsv_empty)"
    local dump="${STATE}/last_payload_${pair}_${tf}.txt"
    printf '%s' "${payload}" | head -c 8000 > "${dump}" 2>/dev/null || true
    log "DEBUG" "${pair} ${tf} dumped_payload=${dump}"
    return 0
  fi

  local pair_o tf_o direction score conf entry sl tp provider rejected filter_str reasons
  IFS=$'\t' read -r pair_o tf_o direction score conf entry sl tp provider rejected filter_str reasons <<< "${tsv}"

  local now
  now="$(ts_iso)"

  # Dedup: skip CSV + Telegram if unchanged.
  if ! signal_is_new "${pair_o}" "${tf_o}" "${direction}" "${score}" "${entry}" "${sl}" "${tp}"; then
    log "DEDUP" "${pair_o} ${tf_o} signal unchanged -> skip"
    return 0
  fi

  # Extract A3 components from reasons for CSV logging
  local _ema_comp _rsi_comp _macd_comp _adx_comp _adx_raw _rsi_raw _macd_hist_raw _macro6 _h1_trend _tier_csv _session _adx_regime=""
  _ema_comp="$(echo "${reasons}" | grep -oP 'ema_comp=\K[\d.]+' || true)"
  _rsi_comp="$(echo "${reasons}" | grep -oP 'rsi_comp=\K[\d.]+' || true)"
  _macd_comp="$(echo "${reasons}" | grep -oP 'macd_comp=\K[\d.]+' || true)"
  _adx_comp="$(echo "${reasons}" | grep -oP 'adx_comp=\K[\d.]+' || true)"
  _adx_raw="$(echo "${reasons}" | grep -oP '(?<![a-z])adx=\K[\d.]+' || true)"
  _rsi_raw="$(echo "${reasons}" | grep -oP '(?<![a-z])rsi=\K[\d.]+' || true)"
  _macd_hist_raw="$(echo "${reasons}" | grep -oP 'macd_hist=\K[-\d.e]+' || true)"
  _macro6="$(echo "${filter_str}" | grep -oP 'macro6=\K\d+' || true)"
  _h1_trend="$(echo "${filter_str}" | grep -oP 'H1_trend_\K\w+' || true)"
  # Tier inline (score_int not yet computed, derive from score float)
  local _score_int_csv
  _score_int_csv="$(python3 -c "import math; print(int(math.floor(float('${score}')+1e-9)))" 2>/dev/null || echo 0)"
  if (( _score_int_csv >= TELEGRAM_TIER_GREEN_MIN_INT )); then _tier_csv="GREEN"
  elif (( _score_int_csv >= TELEGRAM_TIER_YELLOW_MIN_INT )); then _tier_csv="YELLOW"
  else _tier_csv="LOW"; fi
  # Session from UTC hour
  _session="$(python3 -c "
from datetime import datetime, timezone
h=datetime.now(timezone.utc).hour
print('London_open' if 7<=h<9 else 'London' if 9<=h<12 else 'London_NY_overlap' if 12<=h<13 else 'NY' if 13<=h<17 else 'NY_close' if 17<=h<21 else 'Asian')
" 2>/dev/null || true)"
  # ADX regime
  if [[ -n "${_adx_raw}" ]]; then
    _adx_regime="$(python3 -c "print('trending' if float('${_adx_raw}')>=20.0 else 'ranging')" 2>/dev/null || true)"
  fi

  append_alert_csv "${now}" "${pair_o}" "${tf_o}" "${direction}" "${score}" "${conf}" "${entry}" "${sl}" "${tp}" "${provider}" "${rejected}" "${filter_str}" "${reasons}"     "${_ema_comp}" "${_rsi_comp}" "${_macd_comp}" "${_adx_comp}"     "${_adx_raw}" "${_rsi_raw}" "${_macd_hist_raw}"     "${_macro6}" "${_h1_trend}" "${_tier_csv}" "${_session}" "${_adx_regime}"

  if [[ "${rejected}" == "true" ]]; then
    log "FILTER" "${pair_o} ${tf_o} rejected_by_filter score=${score} conf=${conf} filters=${filter_str}"
    return 0
  fi

  log "FILTER" "${pair_o} ${tf_o} accepted score=${score} conf=${conf} filters=${filter_str}"

  local score_int
  score_int="$(SCORE_VAL="${score}" python3 -c '
import os, math
try:
  s=float(os.environ.get("SCORE_VAL","0"))
  print(int(math.floor(s + 1e-9)))
except Exception:
  print(0)
' 2>/dev/null || echo 0)"

  if (( score_int < TELEGRAM_MIN_SCORE )); then
    log "TELEGRAM" "gate: score_int=${score_int} < TELEGRAM_MIN_SCORE=${TELEGRAM_MIN_SCORE} (${pair_o} ${tf_o})"
    return 0
  fi

  local tier emoji
  if (( score_int >= TELEGRAM_TIER_GREEN_MIN_INT )); then
    tier="GREEN"; emoji="🟢"
  elif (( score_int >= TELEGRAM_TIER_YELLOW_MIN_INT )); then
    tier="YELLOW"; emoji="🟡"
  else
    tier="LOW"; emoji="⚪"
  fi

  if [[ "${tier}" == "LOW" ]]; then
    log "TELEGRAM" "tier_skip: score_int=${score_int} < TELEGRAM_TIER_YELLOW_MIN_INT=${TELEGRAM_TIER_YELLOW_MIN_INT} (${pair_o} ${tf_o})"
    return 0
  fi

  if ! telegram_cooldown_check "${pair_o}" "${tf_o}"; then
    log "TELEGRAM" "cooldown active: ${pair_o} ${tf_o}"
    return 0
  fi

  local msg
  if [[ "${tier}" == "GREEN" ]]; then
    msg="${emoji} BotA ${pair_o} ${tf_o} ${direction}\n📊 Score: ${score} | ${filter_str}\n💰 Entry: ${entry}\n🛑 SL: ${sl}  🎯 TP: ${tp}"
  else
    msg="${emoji} BotA ${pair_o} ${tf_o} ${direction} | score=${score} conf=${conf} | ${filter_str}"
  fi

  if send_telegram_message "${msg}"; then
    # Send chart PNG for GREEN signals only
    if [[ "${tier}" == "GREEN" ]] && [[ -f "${TOOLS}/chart_generator.py" ]]; then
      local chart_path
      chart_path="${ROOT}/logs/tmp/chart_${pair_o}_${tf_o}_$$.png"
      python3 "${TOOLS}/chart_generator.py" \
        --pair "${pair_o}" --tf "${tf_o}" \
        --direction "${direction}" \
        --entry "${entry}" --sl "${sl}" --tp "${tp}" \
        --score "${score_int}" --confidence "${score_int}" \
        --out "${chart_path}" >/dev/null 2>>"${ERRLOG}" || true
      if [[ -f "${chart_path}" ]]; then
        curl -s --max-time 15 \
          "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto" \
          -F "chat_id=${TELEGRAM_CHAT_ID}" \
          -F "photo=@${chart_path}" \
          -F "caption=${pair_o} ${tf_o} ${direction} score=${score_int}" \
          >>"${ERRLOG}" 2>&1 || true
        rm -f "${chart_path}" 2>/dev/null || true
        log "CHART" "${pair_o} ${tf_o} chart sent"
      else
        log "CHART" "${pair_o} ${tf_o} chart generation failed"
      fi
    fi
    # Cooldown is only meaningful on real sends (not DRY_RUN, not disabled).
    if ! is_true "${DRY_RUN_MODE:-false}" && ! is_false "${TELEGRAM_ENABLED:-1}"; then
      telegram_cooldown_mark "${pair_o}" "${tf_o}"
    # Publish to ProfitLab dashboard
    if [[ -f "${TOOLS}/supabase_publish.py" ]] && [[ -n "${SUPABASE_SERVICE_KEY:-}" ]]; then
      python3 "${TOOLS}/supabase_publish.py" \
        --pair "${pair_o}" --direction "${direction}" \
        --entry "${entry}" --sl "${sl}" --tp "${tp}" \
        --score "${score_int}" --tf "${tf_o}" --tier "${tier}" \
        2>>"${ERRLOG}" || log "SUPABASE" "publish failed for ${pair_o} ${tf_o}"
    fi
    fi
  else
    log "TELEGRAM" "send failed, cooldown NOT set for ${pair_o} ${tf_o} (will retry next cycle)"
  fi
}

scan_once() {
  local tf pair
  for tf in ${TIMEFRAMES}; do
    for pair in ${PAIRS}; do
      process_pair_tf "${pair}" "${tf}"
    done
  done
}

main() {
  local once="false"
  case "${1:-}" in
    --once) once="true"; shift || true ;;
    --help|-h) usage; exit 0 ;;
    "") ;;
    *) usage; exit 2 ;;
  esac

  load_env_startup
  ensure_alerts_csv

  # Instance locking: prevent overlapping runs.
  local lockfile="${STATE}/watcher.lock"
  exec 9>"${lockfile}"
  if ! flock -n 9; then
    log "WATCHER" "another instance is running (lockfile=${lockfile}), exiting"
    exit 0
  fi

  local mapped="0"
  [[ -n "${_BOTA_MAPPED_FILTER_SCORE_MIN_ALL:-}" ]] && mapped="1"

  log "WATCHER" "SANITY: PAIRS=\"${PAIRS}\" TIMEFRAMES=\"${TIMEFRAMES}\" ALERTS_CSV=\"${ALERTS_CSV}\" DRY_RUN_MODE=\"${DRY_RUN_MODE}\" TELEGRAM_ENABLED=\"${TELEGRAM_ENABLED}\" TELEGRAM_MIN_SCORE=\"${TELEGRAM_MIN_SCORE}\" FILTER_SCORE_MIN=\"${FILTER_SCORE_MIN}\" FILTER_SCORE_MIN_ALL=\"${FILTER_SCORE_MIN_ALL:-}\" MAPPED_FILTER_SCORE_MIN_ALL=\"${mapped}\" TELEGRAM_TIER_YELLOW_MIN=\"${TELEGRAM_TIER_YELLOW_MIN}\" TELEGRAM_TIER_GREEN_MIN=\"${TELEGRAM_TIER_GREEN_MIN}\" TELEGRAM_TIER_YELLOW_MIN_INT=\"${TELEGRAM_TIER_YELLOW_MIN_INT}\" TELEGRAM_TIER_GREEN_MIN_INT=\"${TELEGRAM_TIER_GREEN_MIN_INT}\" CANDLE_MAX_AGE_SECS=\"${CANDLE_MAX_AGE_SECS}\" INDICATOR_LAG_WARN_SECS=\"${INDICATOR_LAG_WARN_SECS}\""

  if [[ "${once}" == "true" ]]; then
    scan_once
    log "DONE" "manual --once scan complete"
    exit 0
  fi

  while true; do
    scan_once
    sleep "${SLEEP_SECONDS}"
  done
}

main "${@}"
