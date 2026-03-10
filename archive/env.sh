#!/usr/bin/env bash
# PURPOSE: Source environment variables from $HOME/BotA/.env for BotA scripts.
# - Returns non-zero instead of exiting the parent shell.
# - Quiet on success (prints only errors).
# - Validates presence of required variables.

set -Eeuo pipefail

ROOT="${HOME}/BotA"
ENV_FILE="${ROOT}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[env] ERROR: Missing $ENV_FILE" >&2
  return 2
fi

# Export all variables defined in the .env file
set -a
. "$ENV_FILE"
set +a

# Minimal validation (quiet warnings allowed)
if [[ -z "${TELEGRAM_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}" ]]; then
  echo "[env] ERROR: TELEGRAM_TOKEN (or TELEGRAM_BOT_TOKEN) is not set in $ENV_FILE" >&2
  return 2
fi

if [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "[env] ERROR: TELEGRAM_CHAT_ID is not set in $ENV_FILE" >&2
  return 2
fi

# Map alternative var name to the one used by sender, if needed
: "${TELEGRAM_TOKEN:=${TELEGRAM_BOT_TOKEN:-}}"

# Success: stay silent
return 0
