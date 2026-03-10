#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# OFFLINE pipeline replay (NO Telegram):
# - Uses tools/replay_mode.sh to compute signal JSON from cache/indicators_<PAIR>_<TF>.json
# - Generates a single run-line compatible with tools/format_card.py
# - Prints the formatted card + JSON path
#
# Usage:
#   tools/pipeline_replay.sh EURUSD M15
#   tools/pipeline_replay.sh EURUSD M15 --sl-mult 1.5 --tp-mult 2.0
#
# Exit codes:
#   0: replay completed (even if direction HOLD / rejected)
#   2: missing inputs/tools

cd /data/data/com.termux/files/home/BotA || { echo "FAIL: BotA folder not found"; exit 2; }

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
  tools/pipeline_replay.sh <PAIR> <TF> [--sl-mult N] [--tp-mult N]

Offline pipeline replay:
  - Generates replay JSON via tools/replay_mode.sh (NO Telegram)
  - Formats a Telegram-ready card via tools/format_card.py (if present)
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
  echo "ERROR: missing PAIR/TF. Example: tools/pipeline_replay.sh EURUSD M15" >&2
  exit 2
fi

if [ ! -x tools/replay_mode.sh ]; then
  echo "ERROR: missing tools/replay_mode.sh (run T32S1 first)" >&2
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUT="state/tmp/pipeline_replay_${PAIR}_${TF}_${TS}.json"

# Generate replay JSON
set +e
./tools/replay_mode.sh "$PAIR" "$TF" --sl-mult "$SL_MULT" --tp-mult "$TP_MULT" > "$OUT"
RC=$?
set -e

# Validate JSON
if ! python3 -m json.tool "$OUT" >/dev/null 2>&1; then
  echo "[PIPELINE] JSON_INVALID rc=$RC out=$OUT"
  exit 0
fi

# Build a single run line for format_card.py (keep stable tokens)
# Expected by format_card (known-good example):
#   [run] EURUSD TF15 decision=BUY score=60 weak=false provider=... age=0.1 price=1.234
RUN_LINE="$(python3 - <<'PY' "$OUT" "$PAIR" "$TF"
import json, sys, math, re
p=sys.argv[1]; pair=sys.argv[2]; tf=sys.argv[3]
d=json.load(open(p))

def f(x, default=0.0):
  try:
    if x is None: return default
    if isinstance(x, bool): return default
    if isinstance(x, (int,float)) and math.isfinite(x): return float(x)
    if isinstance(x, str):
      s=x.strip().replace(",","")
      return float(s)
  except Exception:
    return default
  return default

direction = str(d.get("direction","HOLD")).upper()
score = f(d.get("score",0.0), 0.0)
provider = str(d.get("provider","replay_mode"))
rejected = bool(d.get("filter_rejected", False))
weak = "true" if rejected else "false"
price = f(d.get("price",0.0), 0.0)

# Try to read indicators age_min if present for nicer output; fallback to 0.0
age_min = 0.0
ind_path = f"cache/indicators_{pair}_{tf}.json"
try:
  ind=json.load(open(ind_path))
  age_min = f(ind.get("age_min",0.0), 0.0)
except Exception:
  age_min = 0.0

# TF label like TF15 from M15, TF60 from H1, etc. (best-effort)
tf_tag = "TF?"
m = re.match(r'^[Mm](\d+)$', tf)
if m:
  tf_tag = f"TF{m.group(1)}"
else:
  mh = re.match(r'^[Hh](\d+)$', tf)
  if mh:
    tf_tag = f"TF{int(mh.group(1))*60}"

# Print EXACT run-line format
print(f"[run] {pair} {tf_tag} decision={direction} score={score:.0f} weak={weak} provider={provider} age={age_min:.1f} price={price:.6f}")
PY
)"

echo "[PIPELINE] rc=$RC json=$OUT"
echo "[PIPELINE_RUNLINE] $RUN_LINE"

# Format card if available
if [ -f tools/format_card.py ]; then
  # optional syntax check
  python3 -m py_compile tools/format_card.py >/dev/null 2>&1 || true
  echo "[PIPELINE_CARD] begin"
  printf "%s\n" "$RUN_LINE" | python3 tools/format_card.py || true
  echo "[PIPELINE_CARD] end"
else
  echo "[PIPELINE_CARD] SKIP (missing tools/format_card.py)"
fi

exit 0
