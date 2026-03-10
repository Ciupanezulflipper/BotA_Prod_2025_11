#!/data/data/com.termux/files/usr/bin/bash
# run_with_env.sh
#
# Strict env loader + command runner (Termux-safe)
# Key behavior:
#   - Loads variables from ENV_FILE (default: $HOME/.env)
#   - DOES NOT override variables that are already set in the current shell
#     (so: TELEGRAM_ENABLED=0 bash run_with_env.sh ... will stay 0 even if .env has 1)

set -euo pipefail

ENV_FILE="${ENV_FILE:-$HOME/.env}"

die() { echo "ERROR: $*" >&2; exit 1; }

load_env_nonclobber() {
  [ -f "$ENV_FILE" ] || die "ENV_FILE not found: $ENV_FILE"

  local line key val
  while IFS= read -r line || [ -n "$line" ]; do
    # trim leading spaces
    line="${line#"${line%%[![:space:]]*}"}"

    # skip blanks + comments
    [ -z "$line" ] && continue
    case "$line" in
      \#*) continue ;;
    esac

    # require KEY=VALUE
    if ! [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      die "Invalid line in ENV_FILE ($ENV_FILE): $line"
    fi

    key="${line%%=*}"
    val="${line#*=}"

    # If key already set in environment, do NOT override.
    if [ "${!key+x}" = "x" ]; then
      continue
    fi

    # Strip optional surrounding quotes (simple, safe)
    if [[ "$val" =~ ^\".*\"$ ]]; then
      val="${val:1:${#val}-2}"
    elif [[ "$val" =~ ^\'.*\'$ ]]; then
      val="${val:1:${#val}-2}"
    fi

    export "$key=$val"
  done < "$ENV_FILE"
}

if [ "${1:-}" = "--print" ]; then
  load_env_nonclobber
  echo "ROOT=$HOME/BotA"
  echo "PWD=$(pwd)"
  echo "ENV_FILE=$ENV_FILE"
  echo
  env | grep -E '^(NEWS_|TELEGRAM_|DRY_RUN_MODE=|ENV_FILE=)' | sort
  exit 0
fi

[ "$#" -ge 1 ] || die "Usage: run_with_env.sh [--print] <command> [args...]"

load_env_nonclobber
exec "$@"
