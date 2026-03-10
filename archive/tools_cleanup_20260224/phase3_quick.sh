#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
TOOLS="$HOME/BotA/tools"

# 1) Append fresh snapshots into run.log
"$TOOLS/run_pair.sh" EURUSD >/dev/null
"$TOOLS/run_pair.sh" GBPUSD >/dev/null

# 2) Populate cache for both
python3 "$TOOLS/data_fetch.py" EURUSD
python3 "$TOOLS/data_fetch.py" GBPUSD

# 3) Show cache
python3 "$TOOLS/cache_dump.py" EURUSD GBPUSD
