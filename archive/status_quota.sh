#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
STATE_DIR="$BASE/state"
mkdir -p "$STATE_DIR"

DAY_LIMIT=${DAY_LIMIT:-800}
MIN_LIMIT=${MIN_LIMIT:-8}

now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
day_tag="$(date -u +%Y%m%d)"
day_file="$STATE_DIR/td_hits.${day_tag}.log"
min_window_start="$(date -u -d '-60 seconds' +%s)"

day_used=0
if [[ -f "$day_file" ]]; then
  day_used="$(wc -l < "$day_file" | tr -d ' ')"
fi

min_used=0
if [[ -f "$STATE_DIR/td_hits.log" ]]; then
  while IFS= read -r line; do
    ts="$(echo "$line" | awk '{print $1}' | sed 's/Z$//')"
    if [[ -n "$ts" ]]; then
      s="$(date -u -d "$ts" +%s 2>/dev/null || echo 0)"
      (( s >= min_window_start )) && ((min_used++)) || true
    fi
  done < <(tail -n 400 "$STATE_DIR/td_hits.log" 2>/dev/null || true)
fi

printf "provider=twelve_data day_used=%s/%s (%s%%) minute_used=%s/%s now=%s\n" \
  "$day_used" "$DAY_LIMIT" "$(( day_used*100 / (DAY_LIMIT>0?DAY_LIMIT:1) ))" \
  "$min_used" "$MIN_LIMIT" "$now_iso"
