#!/data/data/com.termux/files/usr/bin/bash
# Detect FX market open (Sun 22:00 UTC → Fri 22:00 UTC)
set -euo pipefail
now=$(date -u +%s)
dow=$(date -u -d "@$now" +%u)   # 1=Mon … 7=Sun
hour=$(date -u -d "@$now" +%H)  # 00-23

if [[ "$dow" -eq 7 ]]; then
  [[ "$hour" -ge 22 ]] && echo Open || echo Closed
elif [[ "$dow" -eq 6 ]]; then
  echo Closed
elif [[ "$dow" -ge 1 && "$dow" -le 4 ]]; then
  echo Open
else # Friday
  [[ "$hour" -lt 22 ]] && echo Open || echo Closed
fi
