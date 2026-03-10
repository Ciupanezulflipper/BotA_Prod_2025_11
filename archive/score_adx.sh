#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/score_adx.sh
# ROLE: ADX-based micro-filter for BotA score fusion.
#
# INPUT  (stdin): single line, e.g.:
#   PAIR=EURUSD TF=M15 VERDICT=SELL BASE_SCORE=29 SESSION=London TIME_UTC=10 MOVE_PIPS=8 ADX=26.8
#
# OUTPUT (stdout): same line + DELTA_ADX, SCORE_ADX, REASON_ADX, e.g.:
#   PAIR=EURUSD ... BASE_SCORE=29 ... ADX=26.8 DELTA_ADX=0 SCORE_ADX=29 REASON_ADX="ADX 20–30 – healthy trend"
#
# NOTES:
#   - Accepts BASE_SCORE= or SCORE= (BASE_SCORE has priority).
#   - Clamps SCORE_ADX to [0,100].
#   - Never crashes; on missing fields, passes through with SCORE_ADX=0 and a reason.

set -euo pipefail

line="$(cat || true)"

# If nothing on stdin, do nothing.
if [[ -z "${line}" ]]; then
  exit 0
fi

# --- Extract base score (prefer BASE_SCORE, fallback SCORE) ---
base_score="$(
  printf '%s\n' "${line}" | sed -n 's/.*BASE_SCORE=\([0-9.]\+\).*/\1/p' | tail -n1
)"
if [[ -z "${base_score}" ]]; then
  base_score="$(
    printf '%s\n' "${line}" | sed -n 's/.*SCORE=\([0-9.]\+\).*/\1/p' | tail -n1
  )"
fi

# --- Extract ADX ---
adx_val="$(
  printf '%s\n' "${line}" | sed -n 's/.*ADX=\([0-9.]\+\).*/\1/p' | tail -n1
)"

# If we still don't have both, append a safe reason and exit.
if [[ -z "${base_score}" || -z "${adx_val}" ]]; then
  # Use 0 if missing to keep downstream logic safe
  safe_score="${base_score:-0}"
  safe_adx="${adx_val:-0}"
  echo "${line} BASE_SCORE=${safe_score} ADX=${safe_adx} DELTA_ADX=0 SCORE_ADX=0 REASON_ADX=\"Missing BASE_SCORE/SCORE or ADX in score_adx.sh input\""
  exit 0
fi

# --- Compute adjusted score based on ADX regime ---
adj_score="$(
  awk -v s="${base_score}" -v a="${adx_val}" 'BEGIN {
    sf = s + 0.0;
    af = a + 0.0;
    f = 1.0;

    # Regimes:
    # <15  -> very weak / choppy (big penalty)
    # 15-20 -> weak (moderate penalty)
    # 20-30 -> normal / healthy (no change)
    # 30-45 -> strong trend (small boost)
    # 45-60 -> very strong (bigger boost, but watch for exhaustion)
    # >60   -> likely exhaustion (small cut)

    if (af < 15.0) {
      f = 0.30;
    } else if (af < 20.0) {
      f = 0.70;
    } else if (af <= 30.0) {
      f = 1.00;
    } else if (af <= 45.0) {
      f = 1.05;
    } else if (af <= 60.0) {
      f = 1.10;
    } else {
      f = 0.90;
    }

    v = sf * f;

    # Clamp to [0,100]
    if (v < 0.0)  v = 0.0;
    if (v > 100.0) v = 100.0;

    # Round to nearest integer
    printf "%.0f", v;
  }'
)"

# Fallback safety if awk fails
if [[ -z "${adj_score}" ]]; then
  adj_score="${base_score}"
fi

# Integer delta
delta=$(( adj_score - ${base_score%.*} ))

# --- Reason text based on ADX regime ---
reason="ADX neutral"

adx_num="${adx_val%.*}"

if awk "BEGIN { exit !(${adx_val} < 15.0) }"; then
  reason="ADX<15 – very weak / choppy trend (big penalty applied)"
elif awk "BEGIN { exit !(${adx_val} < 20.0) }"; then
  reason="ADX 15–20 – weak trend (moderate penalty applied)"
elif awk "BEGIN { exit !(${adx_val} <= 30.0) }"; then
  reason="ADX 20–30 – healthy trend (no score change)"
elif awk "BEGIN { exit !(${adx_val} <= 45.0) }"; then
  reason="ADX 30–45 – strong trend (small boost)"
elif awk "BEGIN { exit !(${adx_val} <= 60.0) }"; then
  reason="ADX 45–60 – very strong trend (extra boost, watch exhaustion)"
else
  reason="ADX>60 – possible trend exhaustion (slight score cut)"
fi

# --- Emit original line + ADX annotations ---
echo "${line} DELTA_ADX=${delta} SCORE_ADX=${adj_score} REASON_ADX=\"${reason}\""
