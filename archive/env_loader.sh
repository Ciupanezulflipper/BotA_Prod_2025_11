#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_DIR"

# Clean CRLF/BOM/zero-width from env files we rely on
for f in .env config/strategy.env config/features.env; do
  [ -f "$f" ] || continue
  sed -i 's/\r$//' "$f" || true
  perl -CSDA -pe 's/\x{FEFF}//g; s/[\x{200B}\x{200E}\x{200F}]//g' -i "$f" 2>/dev/null || true
done

# Load main env chain (root .env first, then config overrides)
set -a
[ -f .env ]               && . .env
[ -f config/strategy.env ] && . config/strategy.env
[ -f config/features.env ] && . config/features.env
set +a

# --- TELEGRAM TOKEN NORMALIZATION ---
: "${TELEGRAM_TOKEN:=${TELEGRAM_BOT_TOKEN:-}}"
export TELEGRAM_TOKEN TELEGRAM_BOT_TOKEN="$TELEGRAM_TOKEN"

# --- PROVIDER KEY NORMALIZATION ---
# Root .env currently defines:
#   ALPHAVANTAGE_API_KEY   (no underscore)
#   TWELVEDATA_API_KEY     (no underscore)
# Signal engine expects:
#   ALPHA_VANTAGE_API_KEY
#   TWELVE_DATA_API_KEY

: "${ALPHA_VANTAGE_API_KEY:=${ALPHAVANTAGE_API_KEY:-}}"
: "${TWELVE_DATA_API_KEY:=${TWELVEDATA_API_KEY:-}}"

export ALPHA_VANTAGE_API_KEY TWELVE_DATA_API_KEY

# Also keep original names exported if they exist
[ -n "${ALPHAVANTAGE_API_KEY:-}" ] && export ALPHAVANTAGE_API_KEY
[ -n "${TWELVEDATA_API_KEY:-}" ]   && export TWELVEDATA_API_KEY

# --- HARD GUARD FOR TELEGRAM TOKEN ---
printf '%s' "${TELEGRAM_TOKEN:-}" | grep -Eq '^[0-9]{7,12}:[A-Za-z0-9_-]{30,}$' \
  || { echo "❌ TELEGRAM_TOKEN regex failed"; exit 1; }
