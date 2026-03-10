#!/data/data/com.termux/files/usr/bin/bash
# fusion_gate.sh - thin shell wrapper around fusion_decider.py
# Contract:
#   - Reads a single JSON object from stdin
#   - Always prints ONE JSON line to stdout (from fusion_decider)
#   - Exit code:
#       0 -> accepted == true
#       1 -> accepted == false OR any error

set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
LOG_DIR="${ROOT}/logs"
mkdir -p "${LOG_DIR}"

tmp_in="$(mktemp)"
trap 'rm -f "$tmp_in"' EXIT

# Read stdin fully into a temp file (so we can re-use it if needed)
cat > "${tmp_in}"

# If empty input, fail-closed with a minimal payload
if [[ ! -s "${tmp_in}" ]]; then
  printf '%s\n' \
    '{"accepted":false,"decision":"WAIT","reason":"fusion_gate:empty_input","fusion":{"pair":"","side":"WAIT","session":"","session_group":"MAIN","fused_score":0.0,"min_fused":60.0,"move_pips":0.0,"min_move_pips":5.0,"base_score":0.0,"macro_score":0.0,"lowvol_score":0.0}}'
  exit 1
fi

# Run the Python decider; capture stdout and respect its exit code
fusion_out=""
fusion_status=0
if ! fusion_out="$(python3 "${TOOLS}/fusion_decider.py" < "${tmp_in}" 2>>"${LOG_DIR}/error.log")"; then
  fusion_status=$?
fi

# If Python crashed or returned non-zero, fail closed.
if [[ ${fusion_status} -ne 0 || -z "${fusion_out}" ]]; then
  printf '%s\n' \
    '{"accepted":false,"decision":"WAIT","reason":"fusion_gate:decider_error","fusion":{"pair":"","side":"WAIT","session":"","session_group":"MAIN","fused_score":0.0,"min_fused":60.0,"move_pips":0.0,"min_move_pips":5.0,"base_score":0.0,"macro_score":0.0,"lowvol_score":0.0}}'
  exit 1
fi

# Validate that we got proper JSON; if not, fail-closed but echo what we saw
if ! printf '%s\n' "${fusion_out}" | jq -e . >/dev/null 2>&1; then
  printf '%s\n' \
    '{"accepted":false,"decision":"WAIT","reason":"fusion_gate:invalid_json_from_decider","fusion":{"pair":"","side":"WAIT","session":"","session_group":"MAIN","fused_score":0.0,"min_fused":60.0,"move_pips":0.0,"min_move_pips":5.0,"base_score":0.0,"macro_score":0.0,"lowvol_score":0.0}}'
  exit 1
fi

# Echo the decider's JSON exactly once
printf '%s\n' "${fusion_out}"

# Interpret the accepted flag and set exit code accordingly
accepted_value="$(printf '%s\n' "${fusion_out}" | jq -r '.accepted // false' 2>/dev/null || echo "false")"

if [[ "${accepted_value}" == "true" ]]; then
  exit 0
else
  exit 1
fi
