#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/tg_probe.sh
# logs raw telegram message BEFORE forwarding to tools/send_tg.sh
# logging is non-fatal; exit code reflects sender result only

set -euo pipefail

ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOG="${ROOT}/logs/tg_probe.log"
SEND="${ROOT}/tools/send_tg.sh"

ts(){ date +%Y-%m-%dT%H:%M:%S%z; }

mode="none"
text=""

if [[ "${1:-}" == "--text" ]]; then
  mode="--text"
  shift || true
  text="${1:-}"
else
  if [[ -t 0 ]]; then
    mode="none"
    text=""
  else
    mode="stdin"
    text="$(cat || true)"
  fi
fi

mkdir -p "${ROOT}/logs" 2>/dev/null || true

# LOG (best effort, never fatal)
{
  echo "----- $(ts) mode=${mode} -----"
  echo "len=${#text}"
  echo -n "repr: "
  printf '%q\n' "$text"
  echo "head:"
  printf '%s\n' "${text:0:200}"
  [[ "$text" == *"<lt;"* ]] && echo "has_<lt;: True" || echo "has_<lt;: False"
  [[ "$text" == *"&lt;"* ]] && echo "has_&lt;: True" || echo "has_&lt;: False"
  [[ "$text" == *"<="* ]] && echo "has_<=: True" || echo "has_<=: False"
  echo
} >> "$LOG" 2>/dev/null || true

# FORWARD (this decides success/failure)
if [[ ! -x "$SEND" ]]; then
  {
    echo "----- $(ts) mode=${mode} -----"
    echo "[probe] ERROR: sender missing/not executable: $SEND"
    echo
  } >> "$LOG" 2>/dev/null || true
  exit 127
fi

if [[ "$mode" == "--text" ]]; then
  bash "$SEND" --text "$text"
  exit $?
elif [[ "$mode" == "stdin" ]]; then
  printf '%s' "$text" | bash "$SEND"
  exit $?
else
  bash "$SEND" "$@"
  exit $?
fi
