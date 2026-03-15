#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/market_open.sh
# DESC: DST-aware FX market gate — London + NY sessions only
# Active window: 07:00-20:00 UTC Mon-Fri
# Sunday 17:00 ET = ~21:00-22:00 UTC — excluded (pre-London)
# Output: "Open" or "Closed"
# Exit: 0 when Open, 1 when Closed

set -euo pipefail

# All logic in UTC to avoid DST confusion
_utc_dow="$(TZ=UTC date +%u)"   # 1=Mon .. 7=Sun
_utc_hm="$(TZ=UTC date +%H%M)"
_utc_int="$((10#$_utc_hm))"

# Saturday UTC: closed all day
if [[ "$_utc_dow" -eq 6 ]]; then
  echo "Closed (weekend Saturday)"
  exit 1
fi

# Sunday UTC: closed all day (Sunday 17:00 ET = ~21:00 UTC — below our 07:00 open anyway)
if [[ "$_utc_dow" -eq 7 ]]; then
  echo "Closed (weekend Sunday)"
  exit 1
fi

# Friday UTC: close at 20:00 UTC (17:00 ET)
if [[ "$_utc_dow" -eq 5 && "$_utc_int" -ge 2000 ]]; then
  echo "Closed (Friday after 20:00 UTC)"
  exit 1
fi

# Skip session filter override
if [[ "${SKIP_SESSION_FILTER:-0}" == "1" ]]; then
  echo "Open (session filter bypassed)"
  exit 0
fi

# Block Asian session: 00:00-07:00 UTC
if [[ "$_utc_int" -lt 700 ]]; then
  echo "Closed (Asian session 00:00-07:00 UTC)"
  exit 1
fi

# Block post-NY: 20:00-24:00 UTC
if [[ "$_utc_int" -ge 2000 ]]; then
  echo "Closed (post-NY 20:00-00:00 UTC)"
  exit 1
fi

echo "Open"
exit 0
