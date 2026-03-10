#!/data/data/com.termux/files/usr/bin/bash
# BotA/tools/send_tg.sh
# Telegram sender with dedupe + FAIL-CLOSED HTML sanitization.
#
# Why:
# - Telegram parse_mode=HTML is strict and will 400 on malformed entities/tags.
#   e.g. raw "rr<=0" must become "rr&lt;=0" (unless inside <code> etc.)
#
# Safety contract:
# - Only these tags are allowed to pass through unchanged (no attributes):
#   <b>, </b>, <code>, </code>, <pre>, </pre>
# - All other '<', '>' and '&' are escaped to &lt; &gt; &amp;
# - Existing supported entities are preserved: &lt; &gt; &amp; &quot; and numeric entities.
#
# Debug:
# - If TG_DEBUG=1, logs raw_len/safe_len and a safe_head preview to logs/send_tg.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${REPO_DIR}/state"
LOG_DIR="${REPO_DIR}/logs"
mkdir -p "${STATE_DIR}" "${LOG_DIR}"

DEDUPE_WINDOW_SEC="${DEDUPE_WINDOW_SEC:-900}"  # 15 minutes

log_line() { printf '%s\n' "$*" >> "${LOG_DIR}/send_tg.log"; }

resolve_env() {
  TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-${BOT_TOKEN:-}}"
  TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${CHAT_ID:-${TG_CHAT_ID:-}}}"

  if [[ -z "${TELEGRAM_TOKEN}" || -z "${TELEGRAM_CHAT_ID}" ]]; then
    if [[ -f "${REPO_DIR}/.env" ]]; then
      # shellcheck disable=SC1090
      . "${REPO_DIR}/.env"
    fi
    TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-${BOT_TOKEN:-}}"
    TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${CHAT_ID:-${TG_CHAT_ID:-}}}"
  fi

  if [[ -z "${TELEGRAM_TOKEN}" || -z "${TELEGRAM_CHAT_ID}" ]]; then
    echo "SEND_TG: missing TELEGRAM_TOKEN/TELEGRAM_CHAT_ID (or BOT_TOKEN/CHAT_ID). Set env or ${REPO_DIR}/.env" >&2
    exit 1
  fi
}

read_text() {
  local text=""
  if [[ "${1:-}" == "--text" ]]; then
    shift
    if [[ $# -lt 1 ]]; then
      echo "SEND_TG: --text requires an argument" >&2
      exit 1
    fi
    text="$*"
  else
    if ! text="$(cat)"; then
      echo "SEND_TG: failed to read stdin" >&2
      exit 1
    fi
  fi

  # Trim leading/trailing whitespace (hash stability)
  text="$(printf "%s" "${text}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  printf '%s' "${text}"
}

sanitize_for_telegram_html() {
  # Reads raw text from stdin, outputs sanitized HTML-safe text.
  # IMPORTANT: uses python3 -c so stdin remains available for message input.
  python3 -c '
import re, sys

s = sys.stdin.read()

ALLOWED = {"<b>","</b>","<code>","</code>","<pre>","</pre>"}
NAMED_ENT = {"&lt;","&gt;","&amp;","&quot;"}

def is_numeric_entity_at(text, i):
    if text.startswith("&#", i):
        m = re.match(r"&#(x[0-9a-fA-F]+|\\d+);", text[i:])
        return m.group(0) if m else None
    return None

out=[]
i=0
n=len(s)

while i<n:
    ch=s[i]

    if ch=="<":
        matched=None
        for t in ALLOWED:
            if s.startswith(t, i):
                matched=t
                break
        if matched:
            out.append(matched); i+=len(matched)
        else:
            out.append("&lt;"); i+=1
        continue

    if ch==">":
        out.append("&gt;"); i+=1
        continue

    if ch=="&":
        kept=None
        for ent in NAMED_ENT:
            if s.startswith(ent, i):
                kept=ent; break
        if kept:
            out.append(kept); i+=len(kept)
            continue

        num=is_numeric_entity_at(s, i)
        if num:
            out.append(num); i+=len(num)
            continue

        out.append("&amp;"); i+=1
        continue

    out.append(ch); i+=1

sys.stdout.write("".join(out))
'
}

dedupe_should_send() {
  local chat_id="$1"
  local text="$2"

  local hash state_file now_epoch last_epoch last_hash delta
  hash="$(printf "%s|%s" "${chat_id}" "${text}" | sha1sum | awk '{print $1}')"
  state_file="${STATE_DIR}/last_tg_${chat_id}.state"

  now_epoch="$(date +%s)"
  last_epoch="0"
  last_hash=""

  if [[ -f "${state_file}" ]]; then
    read -r last_epoch last_hash < "${state_file}" || { last_epoch="0"; last_hash=""; }
  fi

  if [[ -n "${last_hash}" && "${last_hash}" == "${hash}" ]]; then
    delta=$(( now_epoch - last_epoch ))
    if (( delta >= 0 && delta < DEDUPE_WINDOW_SEC )); then
      log_line "[DEDUPE] Skipping duplicate Telegram message (Δ=${delta}s, window=${DEDUPE_WINDOW_SEC}s)"
      return 1
    fi
  fi

  # Update state before sending (prevents spam if sender crashes/retries)
  printf '%s %s\n' "${now_epoch}" "${hash}" > "${state_file}"
  return 0
}

send_message() {
  local text_html="$1"

  local response
  response="$(
    curl -sS \
      -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=${text_html}" \
      -d "parse_mode=HTML"
  )"

  if echo "${response}" | grep -q '"ok":true'; then
    log_line "[SEND_TG] ok $(date -Iseconds)"
    return 0
  fi

  log_line "[SEND_TG] ERROR response: ${response}"
  return 1
}

main() {
  resolve_env

  local raw
  raw="$(read_text "$@")"
  if [[ -z "${raw}" ]]; then
    echo "SEND_TG: empty message, nothing to send" >&2
    exit 0
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "SEND_TG: python3 is required for sanitizer but not found" >&2
    exit 1
  fi

  local safe
  safe="$(printf '%s' "${raw}" | sanitize_for_telegram_html)"

  if [[ -z "${safe}" ]]; then
    log_line "[SEND_TG] ERROR sanitizer produced empty output (raw_len=${#raw})"
    exit 1
  fi

  if [[ "${TG_DEBUG:-0}" == "1" ]]; then
    local head
    head="$(printf '%s' "${safe}" | head -c 220)"
    log_line "[DEBUG] raw_len=${#raw} safe_len=${#safe} safe_head=${head}"
  fi

  if ! dedupe_should_send "${TELEGRAM_CHAT_ID}" "${safe}"; then
    exit 0
  fi

  if send_message "${safe}"; then
    exit 0
  fi

  exit 1
}

main "$@"
