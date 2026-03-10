#!/usr/bin/env bash
#
# tools/score_macro.sh
#
# Macro-filters plugin for BotA scoring pipeline.
#
# GOAL (simple & safe):
#   Take a base score from core indicators and adjust it using ONLY
#   "big picture" context:
#     - Trading session (Asia / London / NewYork / OffHours)
#     - Size of the latest move (MOVE_PIPS)
#     - ADX trend strength (if available)
#
# DESIGN:
#   • Stateless filter: reads ONE line from stdin, prints ONE enriched line.
#   • No network calls, no file writes – safe to use in any pipeline.
#   • Input format: space-separated KEY=VALUE tokens (same style as score_adx.sh).
#
# EXAMPLE USAGE:
#   echo "PAIR=EURUSD TF=M15 VERDICT=SELL SCORE=60 ADX=13.0 MOVE_PIPS=18.1 TIME_UTC=14" \
#     | bash tools/score_macro.sh
#
#   Output (example):
#     PAIR=EURUSD TF=M15 VERDICT=SELL BASE_SCORE=60 SESSION=London \
#     MOVE_PIPS=18.1 ADX=13.0 DELTA_MACRO=-25 SCORE_MACRO=35 \
#     REASON_MACRO="Asia/London chop + post-spike cooldown – conviction reduced"
#
# INTEGRATION IDEA (later step):
#   1) Core engine produces base SCORE and optional:
#        • MOVE_PIPS = absolute move in pips for this candle
#        • ADX       = latest ADX value (same as in alerts.csv)
#        • TIME_UTC  = integer hour 0–23 (UTC) for this candle open/close
#   2) Pipeline calls:
#        ... | bash tools/score_macro.sh | ...
#
#   For now this script can be tested manually via echo as above.

set -euo pipefail

############################
# Helpers
############################

# Numeric comparison helpers using awk to avoid bash float issues.
num_ge() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>=b)}'; }
num_gt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>b)}'; }
num_le() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<=b)}'; }
num_lt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<b)}'; }

# Map UTC hour (0–23) to trading session name.
detect_session() {
  local hour="$1"
  local session="Unknown"

  # Rough session ranges in UTC:
  #   Asia:   22–07
  #   London: 07–16
  #   NY:     12–21
  # Overlaps exist; we pick the "stronger" session in each range.
  if num_ge "$hour" 22 || num_lt "$hour" 7; then
    session="Asia"
  elif num_ge "$hour" 7 && num_lt "$hour" 12; then
    session="London"
  elif num_ge "$hour" 12 && num_lt "$hour" 16; then
    session="London+NY"
  elif num_ge "$hour" 16 && num_lt "$hour" 22; then
    session="NY"
  fi

  echo "$session"
}

############################
# Parse single input line
############################

IFS= read -r line || { echo "ERROR: score_macro.sh expects one input line" >&2; exit 1; }

# Defaults
PAIR=""
TF=""
VERDICT=""
BASE_SCORE=""
ADX=""
MOVE_PIPS=""
TIME_UTC=""
SESSION_OVERRIDE=""

# Parse space-separated KEY=VALUE tokens.
for token in $line; do
  case "$token" in
    PAIR=*)        PAIR="${token#PAIR=}" ;;
    TF=*)          TF="${token#TF=}" ;;
    VERDICT=*)     VERDICT="${token#VERDICT=}" ;;
    SCORE=*)       BASE_SCORE="${token#SCORE=}" ;;        # input name is SCORE
    BASE_SCORE=*)  BASE_SCORE="${token#BASE_SCORE=}" ;;   # allow alternative
    ADX=*)         ADX="${token#ADX=}" ;;
    MOVE_PIPS=*)   MOVE_PIPS="${token#MOVE_PIPS=}" ;;
    TIME_UTC=*)    TIME_UTC="${token#TIME_UTC=}" ;;
    SESSION=*)     SESSION_OVERRIDE="${token#SESSION=}" ;;
  esac
done

if [ -z "${BASE_SCORE:-}" ]; then
  echo "ERROR: score_macro.sh requires SCORE or BASE_SCORE in input line" >&2
  exit 1
fi

############################
# Derive session & defaults
############################

# If TIME_UTC not provided, use current hour in UTC.
if [ -z "${TIME_UTC:-}" ]; then
  TIME_UTC="$(date -u +%H)"
fi

# Infer session unless caller explicitly set SESSION=...
SESSION="${SESSION_OVERRIDE:-$(detect_session "$TIME_UTC")}"

# Defaults for optional values
: "${MOVE_PIPS:=0.0}"
: "${ADX:=0.0}"

############################
# Macro scoring rules
############################

DELTA_MACRO=0
REASON_MACRO="Macro filter: no change"

append_reason() {
  local msg="$1"
  if [ "$REASON_MACRO" = "Macro filter: no change" ]; then
    REASON_MACRO="$msg"
  else
    REASON_MACRO="$REASON_MACRO; $msg"
  fi
}

# 1) Session-based confidence
case "$SESSION" in
  Asia)
    # Penalize noisy Asia session on intraday TFs.
    if [ "$TF" = "M15" ] || [ "$TF" = "M5" ] || [ "$TF" = "M30" ]; then
      DELTA_MACRO=$((DELTA_MACRO - 15))
      append_reason "Asia session on intraday TF – reduce conviction (-15)"
    fi
    ;;
  London+NY)
    # Overlap: small bonus only if already a real signal.
    if num_ge "$BASE_SCORE" 50; then
      DELTA_MACRO=$((DELTA_MACRO + 5))
      append_reason "London+NY overlap – slightly stronger conviction (+5)"
    fi
    ;;
  NY)
    # Neutral for now.
    :
    ;;
  London)
    # Neutral for now.
    :
    ;;
  *)
    # Unknown/off-hours → small penalty.
    DELTA_MACRO=$((DELTA_MACRO - 5))
    append_reason "Unknown/off-hours session – small safety penalty (-5)"
    ;;
esac

# 2) Post-spike cooldown (protect after big moves)
if num_ge "$MOVE_PIPS" 20; then
  DELTA_MACRO=$((DELTA_MACRO - 15))
  append_reason "Big move (${MOVE_PIPS} pips) – post-spike cooldown (-15)"
elif num_ge "$MOVE_PIPS" 12; then
  DELTA_MACRO=$((DELTA_MACRO - 5))
  append_reason "Medium move (${MOVE_PIPS} pips) – slight cooldown (-5)"
fi

# 3) Global cap when ADX is extremely low
FINAL_SCORE="$BASE_SCORE"
FINAL_SCORE=$((FINAL_SCORE + DELTA_MACRO))

if num_lt "$ADX" 15 && num_gt "$FINAL_SCORE" 40; then
  FINAL_SCORE=40
  append_reason "Very low ADX (${ADX}) – cap score at 40 (ranging market)"
fi

# Keep scores in 0–100 bounds.
if [ "$FINAL_SCORE" -lt 0 ]; then
  FINAL_SCORE=0
elif [ "$FINAL_SCORE" -gt 100 ]; then
  FINAL_SCORE=100
fi

############################
# Output enriched line
############################

printf "PAIR=%s "        "${PAIR:-UNKNOWN}"
printf "TF=%s "          "${TF:-UNKNOWN}"
printf "VERDICT=%s "     "${VERDICT:-UNKNOWN}"
printf "BASE_SCORE=%s "  "${BASE_SCORE}"
printf "SESSION=%s "     "${SESSION}"
printf "TIME_UTC=%s "    "${TIME_UTC}"
printf "MOVE_PIPS=%s "   "${MOVE_PIPS}"
printf "ADX=%s "         "${ADX}"
printf "DELTA_MACRO=%s " "${DELTA_MACRO}"
printf "SCORE_MACRO=%s " "${FINAL_SCORE}"
printf "REASON_MACRO=\"%s\"\n" "${REASON_MACRO}"
