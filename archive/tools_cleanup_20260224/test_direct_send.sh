#!/data/data/com.termux/files/usr/bin/bash
# File: $HOME/BotA/tools/test_direct_send.sh
# Purpose: Minimal direct send to verify stdin → sender path.
# Usage: just run; uses embedded chat id in send-tg.sh and token from .env/env.

set -euo pipefail
BOT_DIR="${BOT_DIR:-$HOME/BotA}"
SENDER="$BOT_DIR/tools/send-tg.sh"

[[ -x "$SENDER" ]] || { echo "[FAIL] Missing or non-executable: $SENDER"; exit 1; }

read -r -d '' PAYLOAD <<'TXT' || true
<b>BotA Direct Test</b>
• Expect: PASS
— — — — —
If you see this, stdin → send-tg.sh is GOOD ✅
TXT

"$SENDER" <<< "$PAYLOAD"
echo "[OK] Direct test sent."
