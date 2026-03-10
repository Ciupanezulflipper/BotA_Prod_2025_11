#!/usr/bin/env bash
set -euo pipefail

# env_safe_source.sh <ENV_FILE>
# Safely exports KEY=VALUE pairs from a .env-like file into the current shell
# - supports parentheses, spaces, symbols
# - ignores blank lines and comments
# - does NOT echo values
# - does not execute arbitrary code from the env file

ENV_FILE="${1:-}"
if [ -z "${ENV_FILE}" ]; then
  echo "env_safe_source: missing ENV_FILE argument" >&2
  return 2 2>/dev/null || exit 2
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "env_safe_source: file not found: ${ENV_FILE}" >&2
  return 2 2>/dev/null || exit 2
fi

# Read line-by-line; only accept KEY=VALUE
# KEY must be shell-safe: [A-Za-z_][A-Za-z0-9_]*
while IFS= read -r line || [ -n "$line" ]; do
  # trim leading/trailing whitespace
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"

  # skip blanks and comments
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac

  # require KEY=VALUE
  case "$line" in
    *=*) ;;
    *) continue ;;
  esac

  key="${line%%=*}"
  val="${line#*=}"

  # trim key whitespace
  key="${key#"${key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"

  # validate key name
  if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    continue
  fi

  # remove optional surrounding quotes from value (single or double)
  if [[ "$val" =~ ^\".*\"$ ]]; then
    val="${val:1:-1}"
  elif [[ "$val" =~ ^\'.*\'$ ]]; then
    val="${val:1:-1}"
  fi

  # export without eval (preserves parentheses and symbols)
  export "${key}=${val}"
done < "${ENV_FILE}"
