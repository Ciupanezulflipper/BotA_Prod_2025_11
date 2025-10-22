#!/data/data/com.termux/files/usr/bin/bash
# tools/sim_autorun.sh — simulate periodic scoring without APIs
# Writes ./signals.csv (append-only) for a small watchlist.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.."; pwd)"
export PYTHONPATH="$ROOT"
export DATA_BACKEND="${DATA_BACKEND:-mock}"
export TF="${TF:-5min}"
export LIMIT="${LIMIT:-300}"
export ENGINE="${ENGINE:-v2b}"

WATCH="${WATCH:-EURUSD USDJPY XAUUSD}"
OUT="$ROOT/signals.csv"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

for s in $WATCH; do
  line="$(python "$ROOT/tools/score_offline.py" "$s" || true)"
  echo "[$(ts)] $line"
  # append to signals.csv in a simple format
  printf "%s,%s\n" "$(ts)" "$line" >> "$OUT"
done
