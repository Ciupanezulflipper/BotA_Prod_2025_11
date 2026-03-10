#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Offline test replay mode:
# - Reads cache/indicators_${PAIR}_${TF}.json
# - Computes direction from EMA9/EMA21 + RSI (basic A2)
# - Computes entry=price, SL/TP from ATR multipliers, and rr (risk:reward)
# - NEVER sends Telegram; output is JSON only.
#
# Usage:
#   tools/replay_mode.sh EURUSD M15
#   tools/replay_mode.sh EURUSD M15 --sl-mult 1.5 --tp-mult 2.0
#
# Exit codes:
#   0: JSON emitted (may still include filter_rejected=true with reasons)
#   2: Missing/invalid indicators file or required fields

PAIR="${1:-}"
TF="${2:-}"
shift $(( $#>=2 ? 2 : $# )) || true

SL_MULT="1.5"
TP_MULT="2.0"

while [ $# -gt 0 ]; do
  case "$1" in
    --sl-mult) SL_MULT="${2:-}"; shift 2 ;;
    --tp-mult) TP_MULT="${2:-}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage:
  tools/replay_mode.sh <PAIR> <TF> [--sl-mult N] [--tp-mult N]

Offline replay:
  - Reads cache/indicators_<PAIR>_<TF>.json
  - Computes direction, entry, atr, sl, tp, rr
EOF
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PAIR}" ] || [ -z "${TF}" ]; then
  echo "ERROR: missing PAIR/TF. Example: tools/replay_mode.sh EURUSD M15" >&2
  exit 2
fi

IND="cache/indicators_${PAIR}_${TF}.json"
if [ ! -f "$IND" ]; then
  python3 - <<PY
import json
print(json.dumps({
  "pair": "${PAIR}",
  "tf": "${TF}",
  "provider": "replay_mode",
  "filter_rejected": True,
  "filter_reasons": ["indicators_missing"],
  "reasons": "missing indicators file",
  "entry": 0.0, "sl": 0.0, "tp": 0.0, "rr": 0.0, "atr": 0.0, "price": 0.0,
  "direction": "HOLD", "score": 0, "confidence": 0
}, ensure_ascii=False))
PY
  exit 2
fi

python3 - <<'PY' "$IND" "$PAIR" "$TF" "$SL_MULT" "$TP_MULT"
import json, sys, math
path = sys.argv[1]
pair = sys.argv[2]
tf = sys.argv[3]
sl_mult = float(sys.argv[4])
tp_mult = float(sys.argv[5])

def fnum(x):
  try:
    if x is None or isinstance(x, bool): return None
    if isinstance(x, (int,float)): return float(x)
    if isinstance(x, str):
      s = x.strip().replace(",", "")
      if not s: return None
      return float(s)
  except Exception:
    return None
  return None

raw = open(path, "r", errors="ignore").read().strip()
try:
  d = json.loads(raw)
except Exception as e:
  print(json.dumps({
    "pair": pair, "tf": tf, "provider": "replay_mode",
    "filter_rejected": True, "filter_reasons": ["indicators_invalid_json"],
    "reasons": f"invalid indicators json: {e!r}",
    "entry": 0.0, "sl": 0.0, "tp": 0.0, "rr": 0.0, "atr": 0.0, "price": 0.0,
    "direction": "HOLD", "score": 0, "confidence": 0
  }, ensure_ascii=False))
  sys.exit(2)

price = fnum(d.get("price"))
ema9  = fnum(d.get("ema9"))
ema21 = fnum(d.get("ema21"))
rsi   = fnum(d.get("rsi"))
adx   = fnum(d.get("adx"))
atr   = fnum(d.get("atr"))
atr_pips = fnum(d.get("atr_pips"))
tf_ok = bool(d.get("tf_ok", False))
err   = (d.get("error") or "").strip()

reasons = []
filter_reasons = []
filter_rejected = False

# Basic sanity
if not tf_ok:
  filter_rejected = True
  filter_reasons.append("tf_not_ok")
if err:
  filter_rejected = True
  filter_reasons.append("indicators_error_nonempty")

def direction_from(ema9, ema21, rsi):
  if ema9 is None or ema21 is None or rsi is None:
    return "HOLD"
  if ema9 > ema21 and rsi > 50:
    return "BUY"
  if ema9 < ema21 and rsi < 50:
    return "SELL"
  return "HOLD"

direction = direction_from(ema9, ema21, rsi)

entry = price if price is not None else 0.0
sl = tp = rr = 0.0

# Need atr + price to compute SL/TP/RR
if price is None or not (isinstance(price, (int,float)) and math.isfinite(price) and price > 0):
  filter_rejected = True
  filter_reasons.append("price_invalid")
if atr is None or not (isinstance(atr, (int,float)) and math.isfinite(atr) and atr > 0):
  filter_rejected = True
  filter_reasons.append("atr<=0")

if direction == "HOLD":
  filter_rejected = True
  filter_reasons.append("direction_not_tradeable")

if not filter_rejected and direction in ("BUY","SELL"):
  if direction == "BUY":
    sl = entry - (atr * sl_mult)
    tp = entry + (atr * tp_mult)
    risk = entry - sl
    reward = tp - entry
  else:
    sl = entry + (atr * sl_mult)
    tp = entry - (atr * tp_mult)
    risk = sl - entry
    reward = entry - tp

  rr = (reward / risk) if (risk > 0 and reward > 0) else 0.0
  if rr <= 0:
    filter_rejected = True
    filter_reasons.append("rr<=0")

# Simple score/confidence for replay visibility only (does not affect live gates yet)
score = 0
conf = 40
if not filter_rejected and direction in ("BUY","SELL"):
  score = 60
  conf = 60
  if adx is not None and adx >= 25:  # trend strength bump
    score = 65
    conf = 65

out = {
  "pair": pair,
  "tf": tf,
  "provider": "replay_mode",
  "mode": "replay_offline",
  "direction": direction,
  "price": float(price) if price is not None else 0.0,
  "entry": float(entry) if entry else 0.0,
  "sl": float(sl) if sl else 0.0,
  "tp": float(tp) if tp else 0.0,
  "rr": float(rr) if rr else 0.0,
  "atr": float(atr) if atr is not None else 0.0,
  "atr_pips": float(atr_pips) if atr_pips is not None else 0.0,
  "ema9": float(ema9) if ema9 is not None else 0.0,
  "ema21": float(ema21) if ema21 is not None else 0.0,
  "rsi": float(rsi) if rsi is not None else 0.0,
  "adx": float(adx) if adx is not None else 0.0,
  "tf_ok": tf_ok,
  "ind_error": err,
  "filter_rejected": bool(filter_rejected),
  "filter_reasons": filter_reasons,
  "score": float(score),
  "confidence": float(conf),
}

print(json.dumps(out, ensure_ascii=False))
PY
