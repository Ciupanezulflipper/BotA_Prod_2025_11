#!/data/data/com.termux/files/usr/bin/bash
# Usage:
#   source "$HOME/BotA/tools/tele_env.sh"                # loads from $HOME/BotA/.env
#   source "$HOME/BotA/tools/tele_env.sh" 123456789      # also sets/overrides TELEGRAM_CHAT_ID

set -euo pipefail

ROOT="$HOME/BotA"
ENV_FILE="$ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "[tele_env] ❌ Missing $ENV_FILE (create it with TELEGRAM_BOT_TOKEN=... and TELEGRAM_CHAT_ID=...)" >&2
  return 1 2>/dev/null || exit 1
fi

# load simple KEY=VALUE lines, ignore comments/blank
while IFS='=' read -r k v; do
  # trim whitespace
  k="${k#"${k%%[![:space:]]*}"}"; k="${k%"${k##*[![:space:]]}"}"
  v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
  [ -z "$k" ] && continue
  [[ "$k" =~ ^# ]] && continue
  case "$k" in
    TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)
      export "$k"="$v"
      ;;
    *)
      # ignore unrelated keys
      :
      ;;
  esac
done < "$ENV_FILE"

# Optional positional arg overrides chat id
if [ -n "${1:-}" ]; then
  export TELEGRAM_CHAT_ID="$1"
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "[tele_env] ❌ TELEGRAM_BOT_TOKEN not set (check $ENV_FILE)" >&2
  return 1 2>/dev/null || exit 1
fi

echo "[tele_env] ✅ TELEGRAM_BOT_TOKEN exported"
if [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[tele_env] ✅ TELEGRAM_CHAT_ID = ${TELEGRAM_CHAT_ID}"
else
  echo "[tele_env] ℹ️ TELEGRAM_CHAT_ID not set (you can pass it as an arg to this script)."
fi
