#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/scoring_engine_test.sh
# PURPOSE: Test scoring with cached indicators while market is closed (NO market_open gate).
# IMPORTANT:
#   - Reads indicators from: cache/indicators_${PAIR}_${TF}.json
#   - Does NOT source config/strategy.env (avoids leaking TELEGRAM_TOKEN in bash -x)
#   - Uses only bash + python3 stdlib (no jq)
#   - Missing/empty/invalid JSON => exact stub:
#       {"score":50,"verdict":"HOLD","confidence":50,"reasons":"no_indicators","price":"","provider":"test"}
#
# USAGE:
#   bash tools/scoring_engine_test.sh <PAIR> <TF> [provider]

set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${BOTA_ROOT:-$HOME/BotA}"
CFG="${ROOT}/config/strategy.env"
CACHE="${ROOT}/cache"

PAIR="${1:-EURUSD}"
TF="${2:-H1}"
PROVIDER="${3:-test}"

mkdir -p "${CACHE}"

IND_FILE="${CACHE}/indicators_${PAIR}_${TF}.json"

SE_PAIR="${PAIR}" \
SE_TF="${TF}" \
SE_PROVIDER="${PROVIDER}" \
SE_IND_FILE="${IND_FILE}" \
SE_CFG_FILE="${CFG}" \
python3 - <<'PY'
import os, json, math, re, sys

pair = os.environ.get("SE_PAIR", "EURUSD")
tf = os.environ.get("SE_TF", "H1")
provider = os.environ.get("SE_PROVIDER", "test")
ind_path = os.environ.get("SE_IND_FILE", "")
cfg_path = os.environ.get("SE_CFG_FILE", "")

STUB = {
    "score": 50,
    "verdict": "HOLD",
    "confidence": 50,
    "reasons": "no_indicators",
    "price": "",
    "provider": provider,
}

def emit(obj):
    json.dump(obj, sys.stdout, separators=(",", ":"))
    sys.stdout.flush()

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def safe_float(v, default=0.0):
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default

def read_weights(cfg):
    # Defaults match prior test intent (trend heavy).
    weights = {
        "WEIGHT_TREND": 40.0,
        "WEIGHT_MOMENTUM": 30.0,
        "WEIGHT_RSI": 20.0,
        "WEIGHT_FILTERS": 10.0,
    }
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k not in weights:
                    continue
                v = v.strip().strip('"').strip("'").strip()
                if re.fullmatch(r"[+-]?\d+(\.\d+)?", v or ""):
                    weights[k] = float(v)
    except Exception:
        pass

    s = sum(weights.values()) or 1.0
    return (
        weights["WEIGHT_TREND"] / s,
        weights["WEIGHT_MOMENTUM"] / s,
        weights["WEIGHT_RSI"] / s,
        weights["WEIGHT_FILTERS"] / s,
    )

# --- Required behavior: missing/empty/invalid/non-dict/no-keys => stub ---
REQ_KEYS = ("ema9", "ema21", "rsi", "macd_hist", "adx")
try:
    if (not ind_path) or (not os.path.isfile(ind_path)) or os.path.getsize(ind_path) <= 0:
        emit(STUB); sys.exit(0)

    with open(ind_path, "r", encoding="utf-8") as f:
        ind = json.load(f)

    if not isinstance(ind, dict):
        emit(STUB); sys.exit(0)

    # Treat "{}" or dict without any required keys as no indicators
    if not any(k in ind for k in REQ_KEYS):
        emit(STUB); sys.exit(0)

except Exception:
    emit(STUB); sys.exit(0)

ema9 = safe_float(ind.get("ema9", 0))
ema21 = safe_float(ind.get("ema21", 0))
rsi = safe_float(ind.get("rsi", 50))
macd_hist = safe_float(ind.get("macd_hist", 0))
adx = safe_float(ind.get("adx", 0))

pat_raw = ind.get("pattern", ind.get("patterns", "none"))
if isinstance(pat_raw, list):
    pat_str = " ".join(str(x) for x in pat_raw)
else:
    pat_str = str(pat_raw) if pat_raw is not None else "none"

price_raw = ind.get("price", "")
price = ""
if isinstance(price_raw, (int, float)):
    price = f"{price_raw}"
elif isinstance(price_raw, str):
    price = price_raw.strip()

# Signals
trend_raw = 0
if ema9 > 0 and ema21 > 0:
    if ema9 > ema21:
        trend_raw = 1
    elif ema9 < ema21:
        trend_raw = -1

mom_raw = 0
if macd_hist > 0:
    mom_raw = 1
elif macd_hist < 0:
    mom_raw = -1

rsi_pos = clamp((rsi - 50.0) / 20.0, -1.0, 1.0)
adx_f = clamp(adx / 50.0, 0.0, 1.0)

# Pattern contribution (small bias)
pat = 0.0
lp = pat_str.lower()
if re.search(r"(hammer|bull|engulf|piercing)", lp):
    pat = 0.2
elif re.search(r"(shooting|bear|dark cloud|hanging)", lp):
    pat = -0.2

WT, WM, WR, WF = read_weights(cfg_path)

# Deterministic bounded score
v = (trend_raw * WT) + (mom_raw * WM) + (rsi_pos * WR) + (((adx_f + pat) / 1.2) * WF)
v = clamp(v, -1.0, 1.0)

score = int(round((v + 1.0) * 50.0))
score = int(clamp(score, 0, 100))

verdict = "HOLD"
if score >= 65:
    verdict = "BUY"
elif score <= 35:
    verdict = "SELL"

confidence = score

reasons = []
if ema9 <= 0 or ema21 <= 0:
    reasons.append("EMA_missing")
elif trend_raw > 0:
    reasons.append("EMA9>EMA21")
elif trend_raw < 0:
    reasons.append("EMA9<EMA21")
else:
    reasons.append("EMA_flat")

if mom_raw > 0:
    reasons.append("MACD_up")
elif mom_raw < 0:
    reasons.append("MACD_down")
else:
    reasons.append("MACD_flat")

reasons.append(f"RSI={rsi:.1f}")
reasons.append(f"ADX={adx:.1f}")

if pat_str and pat_str.lower() != "none":
    reasons.append(f"pattern:{pat_str}")

out = {
    "score": score,
    "verdict": verdict,
    "confidence": confidence,
    "reasons": ";".join(reasons),
    "price": price,
    "provider": provider,
}
emit(out)
PY
