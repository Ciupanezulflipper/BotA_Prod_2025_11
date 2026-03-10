#!/data/data/com.termux/files/usr/bin/bash
# tools/send_card_plus_filters.sh — safe HTML for Telegram

set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<summary_line>\" \"<filters_text>\"" >&2
  exit 1
fi

summary_line="$1"
filters_text="${2:-}"

escape_html() {
  local s="${1:-}"
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  # remove any leftover tags: <something>
  s="$(printf '%s' "${s}" | sed -E 's/<[^>]+>//g')"
  echo "${s}"
}

# Build card from summary
card_msg="$(printf '%s\n' "${summary_line}" | "${TOOLS}/format_card.py")"

if [[ -n "${filters_text}" ]]; then
  filt_esc="$(escape_html "${filters_text}")"
  full_msg="${card_msg}"$'\n\n'"🧮 <b>Filter summary</b>"$'\n'"${filt_esc}"
else
  full_msg="${card_msg}"
fi

if [[ -x "${TOOLS}/send-tg.sh" ]]; then
  "${TOOLS}/send-tg.sh" --text "${full_msg}"
else
  echo "[WARN] send-tg.sh missing" >&2
  echo "${full_msg}"
fi
