#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   tools/analyze_now.sh                  # uses env ANALYZE_PAIRS (default: EURUSD GBPUSD)
#   tools/analyze_now.sh EURUSD GBPUSD    # explicit list
#
# Telegram controller can invoke this with arguments; if none are provided
# we fall back to ANALYZE_PAIRS.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

PAIRS=("$@")
if [ ${#PAIRS[@]} -eq 0 ]; then
  IFS=' ,;' read -r -a PAIRS <<< "${ANALYZE_PAIRS:-EURUSD GBPUSD}"
fi

# Delegate to Python (supports multi-pair and pretty rendering)
exec /usr/bin/env python3 "$HERE/analyze_now.py" "${PAIRS[@]}"
