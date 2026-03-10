#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
cd "$ROOT"

# You can override via env:
#   BOT_A_SCALPER_EXPECTED="EURUSD:TF15,GBPUSD:TF15"
#   BOT_A_SCALPER_MAX_AGE_MIN=60
python3 tools/health_scalper.py "$@"
