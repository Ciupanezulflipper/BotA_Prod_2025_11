#!/data/data/com.termux/files/usr/bin/bash
# BotA advanced health check (structure + pipeline) — FAIL-CLOSED
# TERMUX-SAFE / SOURCE-SAFE / NO EXIT-TRAP BUGS / NO INDIRECT EXPANSION

set -u
set -o pipefail

# -------- guard: never kill interactive shell if sourced --------
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  _HC_SOURCED=1
else
  _HC_SOURCED=0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT/tools"
LOGS_DIR="$ROOT/logs"
CACHE_DIR="$ROOT/cache"
TEST_DIR="$ROOT/test_data"
SELF_BASENAME="$(basename "${BASH_SOURCE[0]}")"

FAIL_COUNT=0

_line() { printf '%s\n' "------------------------------------------------------------"; }
_ok()   { printf '%s\n' "[OK] $*"; }
_warn() { printf '%s\n' "[WARN] $*"; }
_fail() { printf '%s\n' "[FAIL] $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

require_cmd() {
  local c="$1"
  command -v "$c" >/dev/null 2>&1 && _ok "command available: $c" || _fail "command missing: $c"
}

require_dir() { [ -d "$1" ] && _ok "dir: $1" || _fail "missing dir: $1"; }
require_file() { [ -f "$1" ] && _ok "exists: $1" || _fail "missing file: $1"; }
require_exec() { [ -x "$1" ] && _ok "exec: $1" || _fail "not executable: $1"; }

print_tail() { [ -f "$1" ] && tail -n "$2" "$1" 2>/dev/null || true; }

# ---------- strict .env loader ----------
_env_load_strict() {
  local env_path="$1" line raw key val
  [ -f "$env_path" ] || { _fail ".env missing at $env_path"; return 1; }

  while IFS= read -r line || [ -n "$line" ]; do
    raw="$line"
    [[ -z "${raw//[[:space:]]/}" ]] && continue
    [[ "$raw" =~ ^# ]] && continue
    [[ "$raw" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || {
      _fail ".env invalid line: $raw"
      return 1
    }
    key="${raw%%=*}"
    val="${raw#*=}"
    [[ "$val" =~ ^\".*\"$ || "$val" =~ ^\'.*\'$ ]] && val="${val:1:${#val}-2}"
    export "$key=$val"
  done < "$env_path"
}

_is_int() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }
_is_num() { [[ "${1:-}" =~ ^[0-9]+([.][0-9]+)?$ ]]; }

# NOTE: Termux bash can throw "invalid indirect expansion" in some environments.
# We avoid ${!k} entirely and use printenv, which is safe under set -u.
_env_get() {
  local k="$1"
  printenv "$k" 2>/dev/null || true
}

_env_required_int_range() {
  local k="$1" min="$2" max="$3"
  local v
  v="$(_env_get "$k")"

  [[ -n "$v" ]] || { _fail "env var missing: $k"; return 1; }
  _is_int "$v" || { _fail "env var not int: $k=$v"; return 1; }
  (( v >= min && v <= max )) || { _fail "env var out of range: $k=$v (expected $min..$max)"; return 1; }
  _ok "env var valid: $k=$v"
  return 0
}

_env_required_num_range() {
  local k="$1" min="$2" max="$3"
  local v
  v="$(_env_get "$k")"

  [[ -n "$v" ]] || { _fail "env var missing: $k"; return 1; }
  _is_num "$v" || { _fail "env var not numeric: $k=$v"; return 1; }

  python3 - <<PY >/dev/null 2>&1 || { _fail "env var out of range: $k=$v (expected $min..$max)"; return 1; }
v=float("$v"); mn=float("$min"); mx=float("$max")
import sys; sys.exit(0 if mn <= v <= mx else 1)
PY

  _ok "env var valid: $k=$v"
  return 0
}

# ---------- repo scan: tools}/ (NO SELF MATCH) ----------
_repo_scan_tools_bad() {
  grep -R --line-number --fixed-strings "tools}/" "$ROOT" \
    --exclude-dir=.git \
    --exclude-dir=__pycache__ \
    --exclude-dir=logs \
    --exclude="$SELF_BASENAME" 2>/dev/null || true
}

# ---------- repo scan: ${TOOLS without } (FUNCTION-SAFE) ----------
_repo_tools_unclosed_scan() {
  local tmp
  tmp="$(mktemp "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/hc_tools.XXXXXX")" || return 2
  trap 'rm -f "${tmp:-}" >/dev/null 2>&1 || true' RETURN

  grep -R --line-number "\${TOOLS" "$ROOT" \
    --exclude-dir=.git \
    --exclude-dir=__pycache__ \
    --exclude-dir=logs \
    --exclude="$SELF_BASENAME" >"$tmp" 2>/dev/null || true

  grep -q "\${TOOLS" "$tmp" && grep -qv "}" "$tmp"
}

# ---------- HEADER ----------
printf '\n'; _line
printf '%s\n' "[HEALTH] BotA advanced health check"
_line
printf '%s\n' "Root: $ROOT"

_line
printf '%s\n' "[HEALTH] dependency check"
_line

require_cmd bash
require_cmd python3
require_cmd grep
require_cmd find
require_cmd printenv

require_dir "$ROOT"
require_dir "$TOOLS_DIR"
require_dir "$LOGS_DIR"
require_dir "$CACHE_DIR"
require_dir "$TEST_DIR"

require_file "$TOOLS_DIR/data_fetch_candles.sh"
require_exec "$TOOLS_DIR/data_fetch_candles.sh"

printf '\n'; _line
printf '%s\n' "[HEALTH] environment"
_line

if _env_load_strict "$ROOT/.env"; then
  _ok ".env loaded"
else
  _fail ".env parse failed"
fi

_env_required_int_range TELEGRAM_ENABLED 0 1 || true
_env_required_int_range DRY_RUN_MODE 0 1 || true
_env_required_int_range FILTER_SCORE_MIN 0 100 || true
_env_required_num_range FILTER_RR_MIN 0.0 10.0 || true

printf '\n'; _line
printf '%s\n' "[HEALTH] repo integrity"
_line

# tools}/ should only be considered a risk if it exists outside this healthcheck file.
bad_tools="$(_repo_scan_tools_bad)"
if [ -n "${bad_tools:-}" ]; then
  _warn "found tools}/ (malformed path substring)"
  printf '%s\n' "$bad_tools" | head -n 20
  _fail "malformed tools}/ detected"
else
  _ok "no tools}/ found (excluding self)"
fi

if _repo_tools_unclosed_scan; then
  _fail "unterminated \${TOOLS detected"
else
  _ok "no unterminated \${TOOLS"
fi

printf '\n'; _line
printf '%s\n' "[HEALTH] error.log tail"
_line
print_tail "$LOGS_DIR/error.log" 50

printf '\n'; _line
if [ "$FAIL_COUNT" -gt 0 ]; then
  _fail "health check FAILED (fail_count=$FAIL_COUNT)"
  [ "$_HC_SOURCED" -eq 1 ] && return 1 || exit 1
fi

_ok "health check PASSED"
[ "$_HC_SOURCED" -eq 1 ] && return 0 || exit 0
