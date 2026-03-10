#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/send-tg.sh
# PURPOSE:
#   Simple Telegram sender for BotA.
#   Supports:
#     • echo "msg" | bash tools/send-tg.sh
#     • bash tools/send-tg.sh --text "msg"
#     • bash tools/send-tg.sh --file /path/to/file
#
# TOKEN RESOLUTION ORDER:
#   BOT_TOKEN > TELEGRAM_BOT_TOKEN > TELEGRAM_TOKEN  (from env or .env.runtime or strategy.env)
# CHAT ID RESOLUTION ORDER:
#   CHAT_ID > TELEGRAM_CHAT_ID

set -euo pipefail

ROOT="${HOME}/BotA"

# --------------------------------------------------------------------
# Load environment (runtime + strategy)
# --------------------------------------------------------------------
if [[ -f "${ROOT}/.env.runtime" ]]; then
  # shellcheck disable=SC1091
  . "${ROOT}/.env.runtime"
fi

if [[ -f "${ROOT}/config/strategy.env" ]]; then
  # shellcheck disable=SC1091
  . "${ROOT}/config/strategy.env"
fi

# --------------------------------------------------------------------
# Resolve token/chat and parse mode
# --------------------------------------------------------------------
TOKEN="${BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}}"
CHAT="${CHAT_ID:-${TELEGRAM_CHAT_ID:-}}"
PARSE_MODE="${TELEGRAM_PARSE_MODE:-HTML}"

if [[ -z "${TOKEN}" || -z "${CHAT}" ]]; then
  echo "[send-tg] missing TOKEN or CHAT_ID (BOT_TOKEN/TELEGRAM_BOT_TOKEN/TELEGRAM_TOKEN, CHAT_ID/TELEGRAM_CHAT_ID)" >&2
  exit 0
fi

# --------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------
MODE="stdin"      # default: read from stdin
TEXT=""
FILE=""

if [[ "${#@}" -gt 0 ]]; then
  case "${1:-}" in
    --text)
      MODE="text"
      TEXT="${2:-}"
      shift 2 || true
      ;;
    --file)
      MODE="file"
      FILE="${2:-}"
      shift 2 || true
      ;;
    *)
      # Unexpected arg → treat as --text "arg..."
      MODE="text"
      TEXT="$*"
      ;;
  esac
fi

# --------------------------------------------------------------------
# Acquire message body
# --------------------------------------------------------------------
case "${MODE}" in
  file)
    if [[ -z "${FILE}" || ! -f "${FILE}" ]]; then
      echo "[send-tg] no message file to send (${FILE:-<empty>})" >&2
      exit 0
    fi
    if [[ ! -s "${FILE}" ]]; then
      echo "[send-tg] message file is empty: ${FILE}" >&2
      exit 0
    fi
    TEXT="$(cat -- "${FILE}")"
    ;;
  text)
    if [[ -z "${TEXT}" ]]; then
      echo "[send-tg] empty --text payload, nothing to send" >&2
      exit 0
    fi
    ;;
  stdin)
    TMP_FILE="$(mktemp -p "${TMPDIR:-/data/data/com.termux/files/usr/tmp}" sendtg_XXXXXX 2>/dev/null || mktemp)"
    cat > "${TMP_FILE}"
    if [[ ! -s "${TMP_FILE}" ]]; then
      echo "[send-tg] stdin was empty, nothing to send" >&2
      rm -f "${TMP_FILE}"
      exit 0
    fi
    TEXT="$(cat -- "${TMP_FILE}")"
    rm -f "${TMP_FILE}"
    ;;
esac

# Safety: trim leading/trailing whitespace
TEXT="$(printf '%s' "${TEXT}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

if [[ -z "${TEXT}" ]]; then
  echo "[send-tg] final TEXT is empty after trimming, nothing to send" >&2
  exit 0
fi

# --------------------------------------------------------------------
# Send via Telegram Bot API
# --------------------------------------------------------------------
# Use --data-urlencode for text to avoid breaking on special chars.
curl -sS -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT}" \
  --data-urlencode "text=${TEXT}" \
  -d "parse_mode=${PARSE_MODE}" >/dev/null 2>&1 || {
    echo "[send-tg] curl sendMessage failed" >&2
    exit 0
  }

# On success: be quiet (no stdout noise)
exit 0
