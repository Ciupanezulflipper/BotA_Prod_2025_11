#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/scoring_engine.sh
# MODE: A3 — 5-component scoring: EMA+RSI+MACD+ADX from cache/indicators_* JSON
#
# GOAL (Step 1):
# - Remove pinned score/confidence=60.0
# - Keep EXACT JSON contract keys used by watcher/quality_filter
# - No new dependencies: bash + python3 (stdlib only). (jq not required here)
#
# Contract keys preserved:
# pair, tf, direction, entry, sl, tp, volatility, score, confidence, reasons,
# price, provider, atr, filter_rr, filter_atr, filter_rejected, filter_reasons,
# pattern_delta
###############################################################################

set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="${ROOT}/tools"
CACHE="${ROOT}/cache"
CFG="${ROOT}/config/strategy.env"

PAIR="${1:-EURUSD}"
TF_RAW="${2:-M15}"

log() { printf '%s\n' "$*" >&2; }

emit_hold_json() {
  local pair="$1"
  local tf="$2"
  local reason="$3"
  local provider="${4:-scoring_engine_shell}"

  EMIT_PAIR="$pair" \
  EMIT_TF="$tf" \
  EMIT_REASON="$reason" \
  EMIT_PROVIDER="$provider" \
  python3 - <<'PY'
import os, json, sys
out = {
  "pair": os.environ.get("EMIT_PAIR",""),
  "tf": os.environ.get("EMIT_TF",""),
  "direction": "HOLD",
  "entry": 0.0,
  "sl": 0.0,
  "tp": 0.0,
  "volatility": "unknown",
  "score": 0,
  "confidence": 40,
  "reasons": os.environ.get("EMIT_REASON",""),
  "price": 0.0,
  "provider": os.environ.get("EMIT_PROVIDER","scoring_engine_shell"),
  "atr": 0.0,
  "filter_rr": 0.0,
  "filter_atr": 0.0,
  "filter_rejected": True,
  "filter_reasons": ["fail_closed"],
  "pattern_delta": 0
}
json.dump(out, sys.stdout, separators=(",",":"))
PY
}

# NEW (Step S4): Closed-path HOLD should preserve numeric context if cache exists.
# Scope: ONLY used for the market-phase Closed emission path.
emit_hold_closed_from_cache() {
  local pair="$1"
  local tf="$2"
  local reason="$3"
  local provider="${4:-scoring_engine_market}"
  local ind_path="${CACHE}/indicators_${pair}_${tf}.json"

  if [[ -f "${ind_path}" ]]; then
    EMIT_PAIR="$pair" \
    EMIT_TF="$tf" \
    EMIT_REASON="$reason" \
    EMIT_PROVIDER="$provider" \
    EMIT_INDIC_PATH="$ind_path" \
    python3 - <<'PY'
import os, json, math, sys

def sf(v, d=0.0):
    try:
        f = float(v)
        return d if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return d

def load(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def volatility_bucket(atr: float, price: float) -> str:
    if atr <= 0.0 or price <= 0.0:
        return "unknown"
    atr_pct = (atr / price) * 100.0
    if atr_pct < 0.05:
        return "low"
    if atr_pct < 0.15:
        return "normal"
    if atr_pct < 0.30:
        return "high"
    return "extreme"

pair = os.environ.get("EMIT_PAIR","")
tf = os.environ.get("EMIT_TF","")
reason = os.environ.get("EMIT_REASON","")
provider = os.environ.get("EMIT_PROVIDER","scoring_engine_market")
path = os.environ.get("EMIT_INDIC_PATH","")

ind = load(path)
price = sf(ind.get("price"))
atr = sf(ind.get("atr"))
vol = volatility_bucket(atr, price)

entry = float(price) if price > 0.0 else 0.0
sl = float(price - atr) if (price > 0.0 and atr > 0.0) else 0.0
tp = float(price + atr) if (price > 0.0 and atr > 0.0) else 0.0

out = {
  "pair": pair,
  "tf": tf,
  "direction": "HOLD",
  "entry": entry,
  "sl": sl,
  "tp": tp,
  "volatility": vol,
  "score": 0,
  "confidence": 40,
  "reasons": reason,
  "price": float(price) if price > 0.0 else 0.0,
  "provider": provider,
  "atr": float(atr) if atr > 0.0 else 0.0,
  "filter_rr": 0.0,
  "filter_atr": 0.0,
  "filter_rejected": True,
  "filter_reasons": ["fail_closed"],
  "pattern_delta": 0
}
json.dump(out, sys.stdout, separators=(",",":"))
PY
  else
    emit_hold_json "${pair}" "${tf}" "${reason}" "${provider}"
  fi
}

fallback_trap() {
  trap - ERR
  log "[SCORING] ERR trap triggered for ${PAIR} ${TF_RAW}"
  emit_hold_json "${PAIR}" "${TF_RAW}" "internal error trap" "scoring_engine_trap"
  exit 0
}
trap 'fallback_trap' ERR

# Load strategy defaults if present (non-fatal).
if [[ -f "${CFG}" ]]; then
  # shellcheck disable=SC1090
  source "${CFG}" 2>/dev/null || true
fi

# Normalize inputs
ENGINE_MODE="${ENGINE_MODE:-CONSERVATIVE}"
ENGINE_MODE="${ENGINE_MODE^^}"

if [[ ! "${PAIR}" =~ ^[A-Z0-9_]{3,10}$ ]]; then
  emit_hold_json "${PAIR}" "${TF_RAW}" "invalid pair" "scoring_engine_input"
  exit 0
fi

case "${PAIR}" in
  EURUSD|GBPUSD|USDJPY|EURJPY) ;;
  *) emit_hold_json "${PAIR}" "${TF_RAW}" "pair not allowed" "scoring_engine_input"; exit 0 ;;
esac

if [[ ! "${TF_RAW}" =~ ^[MmHhDd][0-9]{1,3}$ ]]; then
  emit_hold_json "${PAIR}" "${TF_RAW}" "invalid timeframe" "scoring_engine_input"
  exit 0
fi
TF="${TF_RAW}"

# Market gate:
# - If tools/market_open.sh says "Closed" => fail-closed HOLD.
# - If "Open" => proceed.
# - If missing/Unknown => proceed but tag in reasons (avoid silent blocking).
PHASE="Unknown"
if [[ -x "${TOOLS}/market_open.sh" ]]; then
  _raw="$("${TOOLS}/market_open.sh" 2>/dev/null || true)"
  _raw="$(printf %s "${_raw}" | head -n1 | tr -d '[:space:]')"
  if [[ "${_raw}" == "Open" || "${_raw}" == "Closed" ]]; then
    PHASE="${_raw}"
  fi
  unset _raw
fi
if [[ "${PHASE}" == "Closed" ]]; then
  # ONLY CHANGE IN BEHAVIOR: preserve numeric context from indicators cache if present.
  emit_hold_closed_from_cache "${PAIR}" "${TF}" "market phase Closed" "scoring_engine_market"
  exit 0
fi

INDICATORS_PATH="${CACHE}/indicators_${PAIR}_${TF}.json"
if [[ ! -f "${INDICATORS_PATH}" ]]; then
  emit_hold_json "${PAIR}" "${TF}" "missing indicators file" "indicator_cache"
  exit 0
fi

export SCORING_PAIR="${PAIR}"
export SCORING_TF="${TF}"
export SCORING_MODE="${ENGINE_MODE}"
export SCORING_INDIC_PATH="${INDICATORS_PATH}"
export SCORING_MARKET_PHASE="${PHASE}"

python3 - <<'PY'
import os, json, math, sys

def sf(v, d=0.0):
    try:
        f = float(v)
        return d if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return d

def load(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def volatility_bucket(atr: float, price: float) -> str:
    # ATR as % of price (FX-friendly): stable buckets
    if atr <= 0.0 or price <= 0.0:
        return "unknown"
    atr_pct = (atr / price) * 100.0
    if atr_pct < 0.05:
        return "low"
    if atr_pct < 0.15:
        return "normal"
    if atr_pct < 0.30:
        return "high"
    return "extreme"

pair = os.environ.get("SCORING_PAIR","")
tf = os.environ.get("SCORING_TF","")
phase = os.environ.get("SCORING_MARKET_PHASE","Unknown")
path = os.environ.get("SCORING_INDIC_PATH","")

ind = load(path)

# Fail-closed guard if upstream marked TF mismatch
tf_ok = ind.get("tf_ok", True)
err = ind.get("error", "")
if tf_ok is False or err == "tf_mismatch":
    out = {
      "pair": pair, "tf": tf, "direction": "HOLD",
      "entry": 0.0, "sl": 0.0, "tp": 0.0, "volatility": "unknown",
      "score": 0, "confidence": 40,
      "reasons": "tf_mismatch_detected",
      "price": 0.0, "provider": "engine_A3",
      "atr": 0.0, "filter_rr": 0.0, "filter_atr": 0.0,
      "filter_rejected": True, "filter_reasons": ["fail_closed","tf_mismatch"],
      "pattern_delta": 0
    }
    json.dump(out, sys.stdout, separators=(",",":"))
    sys.exit(0)

ema9  = sf(ind.get("ema9"))
ema21 = sf(ind.get("ema21"))
rsi   = sf(ind.get("rsi"))
atr   = sf(ind.get("atr"))
price = sf(ind.get("price"))

missing = []
if ema9 <= 0:  missing.append("ema9_missing")
if ema21 <= 0: missing.append("ema21_missing")
if rsi <= 0:   missing.append("rsi_missing")
if price <= 0: missing.append("price_missing")

direction = "HOLD"
score = 0.0
confidence = 40.0
reasons = []

if missing:
    reasons = ["indicators_missing"] + missing
    out = {
      "pair": pair, "tf": tf, "direction": "HOLD",
      "entry": 0.0, "sl": 0.0, "tp": 0.0, "volatility": "unknown",
      "score": 0, "confidence": 40,
      "reasons": ",".join(reasons),
      "price": 0.0, "provider": "engine_A3",
      "atr": atr, "filter_rr": 0.0, "filter_atr": 0.0,
      "filter_rejected": True, "filter_reasons": ["fail_closed"] + missing,
      "pattern_delta": 0
    }
    json.dump(out, sys.stdout, separators=(",",":"))
    sys.exit(0)

# Core direction (unchanged intent)
if ema9 > ema21 and rsi > 50:
    direction = "BUY"
elif ema9 < ema21 and rsi < 50:
    direction = "SELL"
else:
    direction = "HOLD"

vol = volatility_bucket(atr, price)

if direction == "HOLD":
    out = {
      "pair": pair, "tf": tf, "direction": "HOLD",
      "entry": 0.0, "sl": 0.0, "tp": 0.0, "volatility": vol,
      "score": 0, "confidence": 40,
      "reasons": f"no_signal|phase={phase}",
      "price": price, "provider": "engine_A3",
      "atr": atr, "filter_rr": 0.0, "filter_atr": 0.0,
      "filter_rejected": True, "filter_reasons": ["no_signal"],
      "pattern_delta": 0
    }
    json.dump(out, sys.stdout, separators=(",",":"))
    sys.exit(0)

# ── ENGINE A3: 5-component scoring ──────────────────────────────────────────
# base=40 + ema_comp(0-20) + rsi_comp(0-15) + macd_comp(0-15) + adx_comp(0-10)
# max=100 | gate=62 | needs 3+ components firing to pass

macd_hist = sf(ind.get("macd_hist"))
adx       = sf(ind.get("adx"))

# 1. EMA separation (trend direction strength)
ema_delta_pct = abs(ema9 - ema21) / ema21 * 100.0 if ema21 != 0 else 0.0
ema_delta_bps = ema_delta_pct * 100.0
ema_comp = min(20.0, ema_delta_bps * 1.0)

# 2. RSI distance from neutral (momentum strength)
rsi_comp = min(15.0, abs(rsi - 50.0) * 0.6)

# 3. MACD histogram confirmation (acceleration)
# Positive hist = buying pressure growing, negative = fading
if direction == "BUY":
    macd_comp = min(15.0, max(0.0, macd_hist * 100000.0)) if macd_hist > 0 else 0.0
else:  # SELL
    macd_comp = min(15.0, max(0.0, -macd_hist * 100000.0)) if macd_hist < 0 else 0.0

# 4. ADX trend strength (is this a real trend or noise?)
# ADX < 15: choppy/ranging = 0pts
# ADX 15-20: weak trend = 3pts
# ADX 20-25: developing trend = 6pts
# ADX 25-30: strong trend = 8pts
# ADX > 30:  very strong trend = 10pts
if adx < 15.0:
    adx_comp = 0.0
elif adx < 20.0:
    adx_comp = 3.0
elif adx < 25.0:
    adx_comp = 6.0
elif adx < 30.0:
    adx_comp = 8.0
else:
    adx_comp = 10.0

# I-04 FIX: Hard ADX regime gate — ranging market = no signal
if adx < 20.0:
    json.dump({"pair": pair, "tf": tf, "direction": "HOLD",
               "score": 0.0, "confidence": 0.0,
               "reasons": f"adx_regime_block|adx={adx:.1f}|ranging_market",
               "entry": 0.0, "sl": 0.0, "tp": 0.0, "volatility": 0.0,
               "price": 0.0, "provider": "engine_A3", "atr": 0.0,
               "filter_rr": 0.0, "filter_atr": 0.0,
               "filter_rejected": True, "filter_reasons": ["adx_regime"],
               "pattern_delta": 0}, sys.stdout, separators=(",",":"))
    sys.exit(0)

# 5. Bollinger Bands component (volatility + price position)
bb_upper  = sf(ind.get("bb_upper", 0.0))
bb_middle = sf(ind.get("bb_middle", 0.0))
bb_lower  = sf(ind.get("bb_lower", 0.0))
bb_squeeze = bool(ind.get("bb_squeeze", False))

bb_comp = 0.0
bb_tag = "bb_neutral"
if bb_upper > 0 and bb_lower > 0 and bb_middle > 0:
    if bb_squeeze:
        bb_comp = -10.0
        bb_tag = "bb_squeeze"
    elif direction == "SELL" and price >= bb_upper * 0.9998:
        bb_comp = 8.0
        bb_tag = "bb_upper_sell"
    elif direction == "BUY" and price <= bb_lower * 1.0002:
        bb_comp = 8.0
        bb_tag = "bb_lower_buy"
    elif direction == "SELL" and price > bb_middle:
        bb_comp = 3.0
        bb_tag = "bb_above_mid_sell"
    elif direction == "BUY" and price < bb_middle:
        bb_comp = 3.0
        bb_tag = "bb_below_mid_buy"
    else:
        bb_comp = -5.0
        bb_tag = "bb_counter"

base = 40.0
score = base + ema_comp + rsi_comp + macd_comp + adx_comp + bb_comp

# Penalty if market phase unknown
if phase not in ("Open", "Closed"):
    score = max(0.0, score - 5.0)
    reasons.append("market_phase_unknown")

score = max(0.0, min(100.0, score))
confidence = score

reasons.extend([
    "ok",
    f"ema_bps={ema_delta_bps:.1f}",
    f"rsi={rsi:.1f}",
    f"macd_hist={macd_hist:.6f}",
    f"adx={adx:.1f}",
    f"ema_comp={ema_comp:.1f}",
    f"rsi_comp={rsi_comp:.1f}",
    f"macd_comp={macd_comp:.1f}",
    f"adx_comp={adx_comp:.1f}",
    f"bb_comp={bb_comp:.1f}",
    f"bb={bb_tag}",
    f"phase={phase}"
])

# GEM 53 FIX: Pip-capped SL/TP (max 20 SL / 40 TP pips)
if direction in ("BUY", "SELL") and price > 0.0 and atr > 0.0:
  sl_dist = min(atr * 1.5, 20 * 0.0001)
  tp_dist = min(atr * 2.5, 40 * 0.0001)
  sl_price = float(price - sl_dist) if direction == "BUY" else float(price + sl_dist)
  tp_price = float(price + tp_dist) if direction == "BUY" else float(price - tp_dist)
  sl_price = round(sl_price, 5)
  tp_price = round(tp_price, 5)
else:
  sl_price = 0.0
  tp_price = 0.0

out = {
  "pair": pair,
  "tf": tf,
  "direction": direction,
  "entry": float(price),
  "sl": sl_price,
  "tp": tp_price,
  "volatility": vol,
  "score": float(round(score, 1)),
  "confidence": float(round(confidence, 1)),
  "reasons": "|".join(reasons),
  "price": float(price),
  "provider": "engine_A3",
  "atr": float(atr),
  "filter_rr": 0.0,
  "filter_atr": 0.0,
  "filter_rejected": False,
  "filter_reasons": [],
  "pattern_delta": 0
}

json.dump(out, sys.stdout, separators=(",",":"))
PY
