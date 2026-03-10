#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
. "$DIR/env_loader.sh"

TOK="$TELEGRAM_TOKEN"
echo "== DIAG =="
echo "TOKEN_LEN: ${#TOK}"
echo -n "REGEX_OK: "; printf '%s' "$TOK" | grep -Eq '^[0-9]{7,12}:[A-Za-z0-9_-]{30,}$' && echo YES || echo NO
echo "CHAT_ID: ${TELEGRAM_CHAT_ID:-unset}"
echo -n "getMe -> " && curl -sS -o /dev/null -w 'HTTP:%{http_code}\n' "https://api.telegram.org/bot$TOK/getMe"
echo -n "getUpdates -> " && curl -sS -o /dev/null -w 'HTTP:%{http_code}\n' "https://api.telegram.org/bot$TOK/getUpdates?timeout=1"
