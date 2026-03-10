#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-$HOME/BotA}"
cd "$REPO"

echo "=== BotA alert sender discovery ==="
echo "[info] repo: $REPO"
echo

# Files to scan: only text Python files (exclude venvs, caches, git, logs)
find_py() {
  find . -type f -name "*.py" \
    -not -path "./.git/*" \
    -not -path "./venv/*" \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*"
}

# Core patterns that indicate an actual Telegram SEND (not just formatting)
# 1) Raw Telegram HTTP call (requests.post/sendMessage or urllib)
# 2) aiogram Bot.send_message / bot.send_message
# 3) python-telegram-bot .send_message / .sendPhoto
# 4) common custom wrappers: send_telegram, telegramalert, send_alert
PATTERNS=(
  'sendMessage'
  'api.telegram.org'
  'requests.post'
  '\.send_message'
  '\.sendPhoto'
  'Bot\.send_message'
  'aiogram'
  'send_telegram'
  'telegramalert'
  'send_alert'
)

# Grep once for speed; then show context for each hit
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "[scan] indexing python files..."
find_py > "$TMP.files"

echo "[scan] searching patterns..."
> "$TMP.matches"
while IFS= read -r file; do
  # Use -n for line numbers; -H to show filenames
  if grep -HnE "$(IFS='|'; echo "${PATTERNS[*]}")" "$file" >/dev/null 2>&1; then
    grep -HnE "$(IFS='|'; echo "${PATTERNS[*]}")" "$file" >> "$TMP.matches"
  fi
done < "$TMP.files"

if [[ ! -s "$TMP.matches" ]]; then
  echo "❌ No obvious Telegram send call sites found."
  echo "   Try widening patterns or confirm which library sends messages."
  exit 1
fi

echo "[result] candidate send sites:"
cut -d: -f1 "$TMP.matches" | sort -u | nl -w2 -s'. ' -
echo

# Show context around each unique match
echo "=== Detailed context (±2 lines) ==="
echo
awk -F: '
  { print $1":"$2 }
' "$TMP.matches" | sort -u | while IFS=: read -r f l; do
  echo "----- ${f}:${l} -----"
  nl -ba -w2 -s'  ' "$f" | sed -n "$((l-2)),$((l+2))p"
  echo
done

echo "=== NEXT STEP ==="
echo "Pick the file/function that actually sends BUY/SELL (not /status)."
echo "Tell me: path + function name, and I will deliver a full replacement"
echo "file that calls increment_trade_cap() only after successful send."
