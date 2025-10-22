#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
. venv/bin/activate
set -a; [ -f .env ] && . .env; set +a
python - <<'PY'
import os
print("FMP:", os.getenv("FMP_API_KEY"))
print("Finnhub:", bool(os.getenv("FINNHUB_API_KEY")))
print("TE client:", os.getenv("TRADINGECONOMICS_CLIENT"))
PY
python main.py
