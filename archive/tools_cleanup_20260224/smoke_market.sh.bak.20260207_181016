#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/smoke_market.sh
set -euo pipefail
ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
CACHE="${ROOT}/cache"
mkdir -p "${LOGS}" "${CACHE}"

ok() { printf "✅ %s\n" "$*"; }
err() { printf "❌ %s\n" "$*" >&2; }

# 1) Syntax checks (fail-fast would exit; use -n to only parse)
bash -n "${TOOLS}/market_open.sh" && ok "market_open.sh syntax OK" || err "market_open.sh syntax ERR"
bash -n "${TOOLS}/watch_wrap_market.sh" && ok "watch_wrap_market.sh syntax OK" || err "watch_wrap_market.sh syntax ERR"
bash -n "${TOOLS}/wrap_watch_market.sh" && ok "wrap_watch_market.sh syntax OK" || err "wrap_watch_market.sh syntax ERR"

# 2) Phase probe
PHASE="Unknown"
if [[ -x "${TOOLS}/market_open.sh" ]]; then
  _raw="$("${TOOLS}/market_open.sh" 2>/dev/null || true)"
  _raw="$(printf %s "${_raw}" | head -n1 | tr -d '[:space:]')"
  if [[ "${_raw}" == "Open" || "${_raw}" == "Closed" ]]; then
    PHASE="${_raw}"
  fi
  unset _raw
fi
printf "🌐 phase probe: %s\n" "$PHASE"

# 3) Wrapper dry run (no secrets, no nohup here)
bash "${TOOLS}/watch_wrap_market.sh" || true

# 4) Dashboard one-liner (does not leak secrets)
if [[ -x "${TOOLS}/hourly_dashboard.sh" ]]; then
  bash "${TOOLS}/hourly_dashboard.sh" | tail -n 1 || true
fi

# 5) Heartbeat age
AGE=$(( $(date +%s) - $(cat "${CACHE}/watcher.heartbeat" 2>/dev/null || echo $(date +%s)) ))
printf "Heartbeat age: %ss\n" "$AGE"
