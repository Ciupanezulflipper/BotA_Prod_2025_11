#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/m15_h1_fusion.sh
# MODE: BotA — M15 + H1 fusion gate + macro6 injection (Option A)
#
# NOISE SEPARATION (2026-01-30)
# - All [M15+H1] debug/info lines go to: logs/fusion.debug.log
# - Only WARN/ERROR lines go to stderr (so logs/error.log stays actionable)
#
# WHAT IT DOES
#   • Runs the existing A2 pipeline for:
#       1) M15  (base entry signal)
#       2) H1   (trend confirmation / veto)
#   • Injects NEWS macro data (macro6) from tools/news_sentiment.py into the
#     output JSON so the watcher/CSV pipeline can consume/audit it.
#
# FUSION LOGIC (strict but not extreme)
#   - START from the M15 filtered signal (already direction+score gated).
#   - If M15 is rejected or not BUY/SELL → return it unchanged (but still enriched
#     with macro6 fields).
#   - Otherwise:
#       * If H1 shows a strong trend in the SAME direction → tag as confirmed.
#       * If H1 shows a strong trend in the OPPOSITE direction → veto the trade:
#           - Set filter_rejected = true
#           - Add "H1_trend_opposite" to filter_reasons
#           - Append "vetoed_by_H1" to reasons
#       * If H1 is HOLD / weak / unclear / rejected → treat as NEUTRAL (no veto).
#
# JSON INPUT / OUTPUT CONTRACT
#   • INPUT:  NONE via stdin. This script internally calls:
#       scoring_engine.sh <PAIR> M15 | quality_filter.py
#       scoring_engine.sh <PAIR> H1  | quality_filter.py
#       news_sentiment.py <PAIR>     (JSON mode; Termux-safe RSS macro engine)
#   • OUTPUT: EXACTLY ONE JSON OBJECT to stdout:
#       - Starts from the M15 JSON (all fields preserved, including pattern_delta).
#       - May modify/add:
#           * filter_rejected   (bool)
#           * filter_reasons    (append H1_* tags + macro6 tag)
#           * reasons           (append "vetoed_by_H1" on veto)
#           * macro6            (int 0..6, neutral=3)
#           * macro_score       (float)
#           * macro_provider    (string: off|none|rss|...)
###############################################################################

set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
mkdir -p "${LOGS}" >/dev/null 2>&1 || true

DEBUG_LOG="${DEBUG_LOG:-${LOGS}/fusion.debug.log}"

PAIR="${1:-EURUSD}"
H1_TREND_MIN_SCORE="${H1_TREND_MIN_SCORE:-40}"

# ---------------------------------------------------------------------------
# Logging helpers
#   - debug/info → logs/fusion.debug.log
#   - warn/error → stderr + debug log
# ---------------------------------------------------------------------------
_log_debug() {
  [[ "${FUSION_DEBUG:-0}" == "1" ]] || return 0
  printf '[M15+H1] %s\n' "$*" >> "${DEBUG_LOG}" 2>/dev/null || true
}

_log_warn() {
  printf '[M15+H1][WARN] %s\n' "$*" >&2
  printf '[M15+H1][WARN] %s\n' "$*" >> "${DEBUG_LOG}" 2>/dev/null || true
}

_log_error() {
  printf '[M15+H1][ERROR] %s\n' "$*" >&2
  printf '[M15+H1][ERROR] %s\n' "$*" >> "${DEBUG_LOG}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Helper: run full A2 pipeline (scoring_engine + quality_filter) for pair/tf
# Returns: single-line JSON on stdout
# ---------------------------------------------------------------------------
run_a2_pipeline() {
  local pair="$1"
  local tf="$2"
  bash "${TOOLS}/scoring_engine.sh" "${pair}" "${tf}" \
    | python3 "${TOOLS}/quality_filter.py"
}

# ---------------------------------------------------------------------------
# Helper: jq wrapper
# ---------------------------------------------------------------------------
jq_field() {
  local json="$1"
  local filter="$2"
  printf '%s\n' "${json}" | jq -r "${filter}"
}

# ---------------------------------------------------------------------------
# Helper: fetch macro6 JSON (fail-closed to neutral macro6=3)
# Sets globals: MACRO6 MACRO_SCORE MACRO_PROVIDER MACRO_TAG
# ---------------------------------------------------------------------------
MACRO6="3"
MACRO_SCORE="0.0"
MACRO_PROVIDER="none"
MACRO_TAG="macro6=3"

fetch_macro() {
  local pair="$1"
  # Short-circuit: skip network call when NEWS_ON is not enabled
  if [[ "${NEWS_ON:-0}" != "1" ]]; then
    MACRO6=3; MACRO_SCORE=0; MACRO_PROVIDER="off"; MACRO_TAG="macro6=3"
    return 0
  fi
  local macro_json=""
  local m6="3"
  local ms="0.0"
  local mp="none"

  macro_json="$(python3 "${TOOLS}/news_sentiment.py" "${pair}" 2>/dev/null | head -n 1 || true)"

  if [[ -n "${macro_json}" ]]; then
    if m6="$(printf '%s\n' "${macro_json}" | jq -r '.macro6 // 3' 2>/dev/null)"; then :; else m6="3"; fi
    if ms="$(printf '%s\n' "${macro_json}" | jq -r '.score // 0.0' 2>/dev/null)"; then :; else ms="0.0"; fi
    if mp="$(printf '%s\n' "${macro_json}" | jq -r '.meta.provider // .meta.source // "none"' 2>/dev/null)"; then :; else mp="none"; fi
  fi

  if ! printf '%s\n' "${m6}" | grep -Eq '^[0-6]$'; then
    m6="3"
  fi

  MACRO6="${m6}"
  MACRO_SCORE="${ms}"
  MACRO_PROVIDER="${mp}"
  MACRO_TAG="macro6=${MACRO6}"

  _log_debug "MACRO: pair=${pair} macro6=${MACRO6} score=${MACRO_SCORE} provider=${MACRO_PROVIDER}"
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

# 1) Base M15 signal
if ! m15_json="$(run_a2_pipeline "${PAIR}" "M15")"; then
  _log_error "M15 A2 pipeline failed for ${PAIR}, emitting fail-closed HOLD JSON."
  m15_json="$(jq -n --arg p "${PAIR}" '{
    pair: $p,
    tf: "M15",
    direction: "HOLD",
    entry: 0.0,
    sl: 0.0,
    tp: 0.0,
    volatility: "unknown",
    score: 0,
    confidence: 0,
    reasons: "m15_h1_fusion_m15_failure",
    price: 0.0,
    provider: "m15_h1_fusion",
    atr: 0.0,
    filter_rr: 0.0,
    filter_atr: 0.0,
    filter_rejected: true,
    filter_reasons: ["m15_h1_fusion_m15_failure"],
    pattern_delta: 0
  }')"
fi

# 1.1) Inject macro6 fields into M15 JSON (always)
fetch_macro "${PAIR}"
m15_json="$(printf '%s\n' "${m15_json}" | jq \
  --argjson macro6 "${MACRO6}" \
  --arg macro_score "${MACRO_SCORE}" \
  --arg macro_provider "${MACRO_PROVIDER}" \
  --arg macro_tag "${MACRO_TAG}" \
  '
  .macro6 = $macro6
  | .macro_score = (try ($macro_score|tonumber) catch 0.0)
  | .macro_provider = $macro_provider
  | .filter_reasons = ((.filter_reasons // []) + [$macro_tag])
  ')"

m15_dir="$(jq_field "${m15_json}" '.direction // "HOLD"')"
m15_score="$(jq_field "${m15_json}" '.score // 0')"
m15_filter_rejected="$(jq_field "${m15_json}" '.filter_rejected // false')"
m15_adx="$(jq_field "${m15_json}" '.adx // 0')"

_log_debug "M15 base: pair=${PAIR} dir=${m15_dir} score=${m15_score} rejected=${m15_filter_rejected}"

# If M15 rejected or not BUY/SELL, return unchanged.
if [[ "${m15_filter_rejected}" == "true" ]] || [[ "${m15_dir}" != "BUY" && "${m15_dir}" != "SELL" ]]; then
  _log_debug "M15 rejected or non-tradeable; skipping H1 fusion."
  printf '%s\n' "${m15_json}"
  exit 0
fi

# 2) H1 trend check
h1_json="$(run_a2_pipeline "${PAIR}" "H1")" || {
  _log_error "H1 A2 pipeline failed for ${PAIR}, treating H1 as neutral."
  printf '%s\n' "${m15_json}"
  exit 0
}

h1_dir="$(jq_field "${h1_json}" '.direction // "HOLD"')"
h1_score="$(jq_field "${h1_json}" '.score // 0')"
h1_filter_rejected="$(jq_field "${h1_json}" '.filter_rejected // false')"

_log_debug "H1 trend: pair=${PAIR} dir=${h1_dir} score=${h1_score} rejected=${h1_filter_rejected}"

trend_tag="H1_trend_neutral"
veto="false"

# Pre-fetch H4 direction from indicators cache to guard H1 neutral override
h4_ind_path="${CACHE:-${ROOT}/cache}/indicators_${PAIR}_H4.json"
h4_dir_cached="HOLD"
if [[ -f "${h4_ind_path}" ]]; then
  h4_dir_cached="$(python3 -c "
import json,sys
try:
  d=json.load(open('${h4_ind_path}'))
  e9=float(d.get('ema9',0)); e21=float(d.get('ema21',0))
  print('SELL' if e9 < e21 else ('BUY' if e9 > e21 else 'HOLD'))
except: print('HOLD')
" 2>/dev/null || echo "HOLD")"
fi
h4_opposing="false"
if [[ "${m15_dir}" == "BUY" && "${h4_dir_cached}" == "SELL" ]]; then h4_opposing="true"; fi
if [[ "${m15_dir}" == "SELL" && "${h4_dir_cached}" == "BUY" ]]; then h4_opposing="true"; fi
_log_debug "H4 pre-check: pair=${PAIR} h4_dir=${h4_dir_cached} m15_dir=${m15_dir} h4_opposing=${h4_opposing}"

if [[ "${h1_filter_rejected}" == "true" ]]; then
  _log_debug "H1 rejected by quality filter; neutral for fusion."
  m15_score_int="$(printf '%s\n' "${m15_score:-0}" | awk '{printf("%d", $1)}')"
  h1_override_score="${H1_VETO_OVERRIDE_SCORE:-85}"
  if (( m15_score_int >= h1_override_score )) && [[ "${h4_opposing}" != "true" ]]; then
    trend_tag="H1_trend_neutral_overridden"
    veto="false"
    _log_debug "H1 neutral veto OVERRIDDEN by high score: ${m15_score_int}>=${h1_override_score} (H4 aligned)"
  elif (( m15_score_int >= h1_override_score )) && [[ "${h4_opposing}" == "true" ]]; then
    trend_tag="H1_trend_neutral"
    veto="true"
    _log_debug "H1 neutral override BLOCKED by H4 opposition: h4=${h4_dir_cached} m15=${m15_dir}"
  else
    veto="true"
  fi
else
  if [[ "${h1_dir}" == "BUY" || "${h1_dir}" == "SELL" ]]; then
    h1_score_int="$(printf '%s\n' "${h1_score}" | awk '{printf("%d", $1)}')"
    h1_min_int="$(printf '%s\n' "${H1_TREND_MIN_SCORE}" | awk '{printf("%d", $1)}')"
    if (( h1_score_int >= h1_min_int )); then
      if [[ "${h1_dir}" == "${m15_dir}" ]]; then
        trend_tag="H1_trend_confirmed"
        veto="false"
      else
        trend_tag="H1_trend_opposite"
        # Score override: if M15 score very high AND strong trend, bypass H1 veto
        m15_score_int="$(printf '%s\n' "${m15_score:-0}" | awk '{printf("%d", $1)}')"
        m15_adx_int="$(printf '%s\n' "${m15_adx:-0}" | awk '{printf("%d", $1)}')"
        h1_override_score="${H1_VETO_OVERRIDE_SCORE:-85}"
        h1_override_adx="${H1_VETO_OVERRIDE_ADX:-40}"
        if (( m15_score_int >= h1_override_score && m15_adx_int >= h1_override_adx )); then
          trend_tag="H1_trend_opposite_overridden"
          veto="false"
          _log_debug "H1 veto OVERRIDDEN: score=${m15_score_int}>=${h1_override_score} ADX=${m15_adx_int}>=${h1_override_adx}"
        else
          veto="true"
        fi
      fi
    else
      trend_tag="H1_trend_weak"
      veto="false"
    fi
  else
    m15_score_int="$(printf '%s\n' "${m15_score:-0}" | awk '{printf("%d", $1)}')"
    h1_override_score="${H1_VETO_OVERRIDE_SCORE:-85}"
    if (( m15_score_int >= h1_override_score )) && [[ "${h4_opposing}" != "true" ]]; then
      trend_tag="H1_trend_neutral_overridden"
      veto="false"
      _log_debug "H1 neutral veto OVERRIDDEN by high score: ${m15_score_int}>=${h1_override_score} (H4 aligned)"
    elif (( m15_score_int >= h1_override_score )) && [[ "${h4_opposing}" == "true" ]]; then
      trend_tag="H1_trend_neutral"
      veto="true"
      _log_debug "H1 neutral override BLOCKED by H4 opposition: h4=${h4_dir_cached} m15=${m15_dir}"
    else
      trend_tag="H1_trend_neutral"
      veto="true"
    fi
  fi
fi

_log_debug "Fusion decision: pair=${PAIR} M15_dir=${m15_dir} H1_dir=${h1_dir} trend=${trend_tag} veto=${veto}"

# 3) Apply fusion decision to M15 JSON
if [[ "${veto}" == "true" ]]; then
  fused_json="$(printf '%s\n' "${m15_json}" | jq \
    --arg tag "${trend_tag}" \
    '
    .filter_rejected = true
    | .filter_reasons = ((.filter_reasons // []) + [$tag])
    | .reasons = (
        if .reasons == "" or .reasons == null then
          "vetoed_by_H1"
        else
          (.reasons + ", vetoed_by_H1")
        end
      )
    ')"
  printf '%s\n' "${fused_json}"
  exit 0
fi

# MTF FIX: H4+D1 confluence veto via emit_snapshot.py
mtf_snap="$(python3 "${TOOLS}/emit_snapshot.py" "${PAIR}" 2>/dev/null || true)"
h4_vote="$(printf '%s\n' "${mtf_snap}" | grep '^H4:' | grep -oP 'vote=[+-]?[0-9]+' | cut -d= -f2 || echo 0)"
d1_vote="$(printf '%s\n' "${mtf_snap}" | grep '^D1:' | grep -oP 'vote=[+-]?[0-9]+' | cut -d= -f2 || echo 0)"
h4_vote="${h4_vote:-0}"; d1_vote="${d1_vote:-0}"
mtf_veto="false"
if [[ "${m15_dir}" == "BUY" ]] && (( h4_vote < 0 && d1_vote < 0 )); then mtf_veto="true"; fi
if [[ "${m15_dir}" == "SELL" ]] && (( h4_vote > 0 && d1_vote > 0 )); then mtf_veto="true"; fi
if [[ "${mtf_veto}" == "true" ]]; then
  _log_debug "MTF veto: ${PAIR} M15=${m15_dir} H4=${h4_vote} D1=${d1_vote}"
  printf '%s\n' "${m15_json}" | jq '.' | jq \
    '.filter_rejected=true | .filter_reasons=((.filter_reasons//[])+["H4_D1_oppose"]) | .reasons=(if .reasons=="" or .reasons==null then "vetoed_by_H4_D1" else (.reasons+", vetoed_by_H4_D1") end)'
  exit 0
fi

fused_json="$(printf '%s\n' "${m15_json}" | jq \
  --arg tag "${trend_tag}" \
  '
  .filter_reasons = ((.filter_reasons // []) + [$tag])
  ')"

printf '%s\n' "${fused_json}"
exit 0
