#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Load creds from env or tele.env
if [[ -z "${BOT_TOKEN:-}" || -z "${CHAT_ID:-}" ]]; then
  [[ -f "$HOME/bot-a/config/tele.env" ]] && . "$HOME/bot-a/config/tele.env" || true
fi

msg="${1:-}"
[[ -z "${msg}" ]] && msg="$(cat -)" || true

token="${BOT_TOKEN:-}"; chat="${CHAT_ID:-}"
if [[ -z "$token" || -z "$chat" ]]; then
  echo "SEND_TG: missing BOT_TOKEN/CHAT_ID. Set env or ~/bot-a/config/tele.env" >&2
  exit 2
fi

mask_token="${token:0:9}****"
echo "SEND_TG: chat=${chat} token=${mask_token}"

resp="$(curl -sS -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d chat_id="${chat}" -d parse_mode="Markdown" \
        --data-urlencode text="${msg}")" || {
  echo "SEND_TG: curl failed" >&2; exit 3; }

echo "SEND_TG RESP: ${resp}"

ok="$(printf '%s' "$resp" | grep -o '"ok":[^,}]*' | cut -d: -f2 || true)"
code="$(printf '%s' "$resp" | grep -o '"error_code":[0-9]*' | cut -d: -f2 || true)"
desc="$(printf '%s' "$resp" | grep -o '"description":"[^"]*' | cut -d\" -f4 || true)"

if [[ "${ok}" != "true" ]]; then
  echo "SEND_TG: failed code=${code:-?} desc='${desc:-?}'" >&2
  exit 4
fi
