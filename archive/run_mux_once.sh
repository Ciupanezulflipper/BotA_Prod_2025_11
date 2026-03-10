#!/usr/bin/env bash
set -euo pipefail

# Load BotA runtime env (if any)
[ -f "$HOME/.env.runtime" ] && set -a && . "$HOME/.env.runtime" && set +a

# Read arguments: SYMBOL, TF (minutes), LIMIT (optional)
SYMBOL="${1:-EURUSD}"
TF="${2:-15}"
LIMIT="${3:-150}"

# Call provider_mux.py with positional args (sym tf limit)
python3 "$HOME/BotA/tools/provider_mux.py" "$SYMBOL" "$TF" "$LIMIT" \
  | python3 - <<'PY'
import sys, json, statistics as st
j = json.loads(sys.stdin.read())
rows = j.get("rows", [])
cl = [r["c"] for r in rows[-30:]] if rows else []
last = rows[-1]["c"] if rows else "NA"
print(f"[run] provider={j.get('provider')} bars={len(rows)} last={last} ma={(sum(cl)/len(cl) if cl else 0):.5f}")
PY
