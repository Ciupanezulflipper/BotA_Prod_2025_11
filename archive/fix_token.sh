#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")"/.. 2>/dev/null && pwd)"
cd "$REPO_DIR"

ENV_FILE="config/strategy.env"
mkdir -p config
[ -f "$ENV_FILE" ] || : > "$ENV_FILE"

# Clean CRLF/BOM/zero-widths
sed -i 's/\r$//' "$ENV_FILE"
perl -CSDA -pe 's/\x{FEFF}//g; s/[\x{200B}\x{200E}\x{200F}]//g' -i "$ENV_FILE"

# Load whatever is present
set -a; . "$ENV_FILE" 2>/dev/null || true; set +a

# Accept either variable name; prefer an actually valid one
re='^[0-9]{7,12}:[A-Za-z0-9_-]{30,}$'
ok_env=0; ok_bot=0
[ -n "${TELEGRAM_TOKEN:-}" ]      && printf %s "$TELEGRAM_TOKEN"      | grep -Eq "$re" && ok_env=1 || true
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && printf %s "$TELEGRAM_BOT_TOKEN" | grep -Eq "$re" && ok_bot=1 || true

if   [ "$ok_env" -eq 1 ]; then tok="$TELEGRAM_TOKEN"
elif [ "$ok_bot" -eq 1 ]; then tok="$TELEGRAM_BOT_TOKEN"
else
  echo "⚠️ Paste FULL bot token (digits:secret). Input hidden:"
  read -r -s tok; echo
fi

printf %s "$tok" | grep -Eq "$re" || { echo "❌ Invalid token (must contain a colon)."; exit 1; }

# Write BOTH keys so nothing can override later
grep -q '^TELEGRAM_TOKEN='      "$ENV_FILE" && sed -i "s|^TELEGRAM_TOKEN=.*|TELEGRAM_TOKEN=$tok|"           "$ENV_FILE" || echo "TELEGRAM_TOKEN=$tok" >> "$ENV_FILE"
grep -q '^TELEGRAM_BOT_TOKEN='  "$ENV_FILE" && sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$tok|"   "$ENV_FILE" || echo "TELEGRAM_BOT_TOKEN=$tok" >> "$ENV_FILE"

chmod 600 "$ENV_FILE"
set -a; . "$ENV_FILE"; set +a

echo "🔎 Re-running telegram_diag..."
bash tools/telegram_diag.sh
