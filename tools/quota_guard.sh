#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/quota_guard.sh
# PURPOSE: Lightweight token-bucket + daily-cap guard for a provider (default: twelve_data).
# EXIT CODES:
#   0  = allowed
#   88 = provider missing / env not ready (reserved; not used by default)
#   97 = daily cap exceeded
#   98 = state I/O error
#   99 = invalid args
set -euo pipefail

# -------- Config (env-overridable) --------
PROVIDER="${PROVIDER:-twelve_data}"
COST=1
# Free TwelveData commonly ~8/min, ~800/day; keep headroom by default.
TD_PER_MIN="${TD_PER_MIN:-8}"
TD_DAY_CAP="${TD_DAY_CAP:-760}"

BASE_DIR="${BASE_DIR:-$HOME/BotA}"
STATE_DIR="${STATE_DIR:-$BASE_DIR/state}"
BUCKET_FILE="${BUCKET_FILE:-$STATE_DIR/${PROVIDER}_bucket.state}"

mkdir -p "$STATE_DIR" || true

usage() { echo "usage: $0 [--provider NAME] [--cost N]" >&2; exit 99; }

# -------- Args --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) PROVIDER="${2:-}"; shift 2;;
    --cost)     COST="${2:-}"; shift 2;;
    -h|--help)  usage;;
    *)          usage;;
  esac
done

if [[ -z "${PROVIDER}" ]] || [[ -z "${COST}" ]]; then usage; fi

# -------- Provider env presence (warn-only by default) --------
if [[ "$PROVIDER" == "twelve_data" ]]; then
  : "${TWELVEDATA_API_KEY:=}"
  # If you want to block when key is missing, uncomment next line:
  # [[ -z "$TWELVEDATA_API_KEY" ]] && exit 88
fi

# -------- Load state (or defaults) --------
now_epoch="$(date +%s)"
now_day="$(date -u +%F)"         # YYYY-MM-DD (UTC)
now_min_epoch="$(( now_epoch / 60 ))"

day_ymd="$now_day"
day_used=0
minute_epoch="$now_min_epoch"
minute_used=0

if [[ -f "$BUCKET_FILE" ]]; then
  # shellcheck disable=SC1090
  . "$BUCKET_FILE" || true
fi

# -------- Day rollover --------
if [[ "$day_ymd" != "$now_day" ]]; then
  day_ymd="$now_day"
  day_used=0
  minute_epoch="$now_min_epoch"
  minute_used=0
fi

# -------- Daily cap check --------
if (( day_used + COST > TD_DAY_CAP )); then
  echo "[quota_guard] BLOCK daily cap: used=$day_used cap=$TD_DAY_CAP provider=$PROVIDER" >&2
  exit 97
fi

# -------- Minute window (token-bucket-ish) --------
if (( minute_epoch != now_min_epoch )); then
  minute_epoch="$now_min_epoch"
  minute_used=0
fi

if (( minute_used + COST > TD_PER_MIN )); then
  secs_left="$(( 60 - (now_epoch % 60) ))"
  if (( secs_left > 0 )); then
    echo "[quota_guard] Waiting ${secs_left}s to respect ${TD_PER_MIN}/min (provider=$PROVIDER)" >&2
    sleep "$secs_left"
  fi
  now_epoch="$(date +%s)"
  now_min_epoch="$(( now_epoch / 60 ))"
  minute_epoch="$now_min_epoch"
  minute_used=0
fi

# -------- Consume tokens --------
day_used=$(( day_used + COST ))
minute_used=$(( minute_used + COST ))

# -------- Persist (atomic) --------
tmpf="${BUCKET_FILE}.tmp.$$"
{
  echo "day_ymd=$day_ymd"
  echo "day_used=$day_used"
  echo "minute_epoch=$minute_epoch"
  echo "minute_used=$minute_used"
} > "$tmpf" || { echo "[quota_guard] state write failed" >&2; exit 98; }
mv -f "$tmpf" "$BUCKET_FILE"

exit 0
