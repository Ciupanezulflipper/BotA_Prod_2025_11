#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${REPO:-$HOME/BotA}"
CAP_DIR="${CAP_DIR:-$HOME/bot-a/logs}"
CAP_FILE="${CAP_FILE:-$CAP_DIR/trade_cap.json}"

mkdir -p "$CAP_DIR"

today_utc() { date -u +%F; }

print_status() {
  local today; today="$(today_utc)"
  if [ -f "$CAP_FILE" ]; then
    local raw; raw="$(cat "$CAP_FILE" 2>/dev/null || true)"
    local count day
    count="$(printf '%s' "$raw" | sed -n 's/.*"count"[[:space:]]*:[[:space:]]*\([0-9]\+\).*/\1/p' | head -n1 || true)"
    day="$(printf '%s' "$raw" | sed -n 's/.*"day"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1 || true)"
    echo "[cap] file: $CAP_FILE"
    echo "[cap] raw : $raw"
    echo "[cap] parse: count=${count:-<nil>} day=${day:-<nil>} (today_utc=$today)"
    if [ -n "${count:-}" ] && [ -n "${day:-}" ]; then
      if [ "$day" = "$today" ]; then
        echo "[cap] status: OK (current day)"
      else
        echo "[cap] status: STALE (day != today UTC) — core will roll on write"
      fi
    else
      echo "[cap] status: MALFORMED — use 'reset' to repair"
    fi
  else
    echo "[cap] file: $CAP_FILE (missing)"
    echo "[cap] status: MISSING — use 'reset' to create"
  fi
}

reset_cap() {
  local today; today="$(today_utc)"
  printf '{"count": %s, "day": "%s"}\n' "0" "$today" > "$CAP_FILE".tmp
  mv -f "$CAP_FILE".tmp "$CAP_FILE"
  chmod 600 "$CAP_FILE" || true
  echo "[cap] reset → $(cat "$CAP_FILE")"
}

set_count() {
  local val="$1"
  local today; today="$(today_utc)"
  if ! printf '%s' "$val" | grep -qE '^[0-9]+$'; then
    echo "[cap] error: count must be integer" >&2
    exit 2
  fi
  printf '{"count": %s, "day": "%s"}\n' "$val" "$today" > "$CAP_FILE".tmp
  mv -f "$CAP_FILE".tmp "$CAP_FILE"
  chmod 600 "$CAP_FILE" || true
  echo "[cap] set count=$val → $(cat "$CAP_FILE")"
}

cmd="${1:-status}"
case "$cmd" in
  status) print_status ;;
  reset)  reset_cap ;;
  set)    set_count "${2:-0}" ;;
  *) echo "usage: $0 {status|reset|set N}" >&2; exit 1 ;;
esac
