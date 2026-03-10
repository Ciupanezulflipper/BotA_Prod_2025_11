#!/usr/bin/env bash
# FILE: $HOME/BotA/tools/loop_guard.sh
# MODE: 0755
# PURPOSE: Single-instance guardian. Starts run_loop.sh if not running.

set -Eeuo pipefail
umask 022

ROOT="${BOT_ROOT:-$HOME/BotA}"
TOOLS="$ROOT/tools"
RUN="$TOOLS/run_loop.sh"
STATE="$ROOT/state"
LOGS="$ROOT/logs"
mkdir -p "$STATE" "$LOGS"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
info(){ printf '[INFO] %s %s\n' "$(ts)" "$*"; }
warn(){ printf '[WARN] %s %s\n' "$(ts)" "$*" >&2; }
err() { printf '[ERROR] %s %s\n' "$(ts)" "$*" >&2; }

main() {
  info "loop_guard path=$0 pid=$$"

  if [ ! -x "$RUN" ]; then
    if [ -f "$RUN" ]; then
      chmod +x "$RUN"
    else
      err "missing or non-executable run_loop.sh"
      info "loop_guard cleanup done"
      exit 1
    fi
  fi

  if pgrep -f "BotA/tools/run_loop\.sh" >/dev/null 2>&1; then
    info "run_loop already active — nothing to do"
    info "loop_guard cleanup done"
    exit 0
  fi

  if [ "${1:-check}" = "daemon" ]; then
    info "starting daemon (guarded)"
  fi

  nohup bash "$RUN" daemon >/dev/null 2>&1 & disown
  sleep 1

  if pid=$(pgrep -f "BotA/tools/run_loop\.sh" | head -n1); then
    info "daemon pid=$pid started successfully"
  else
    err "failed to start daemon"
    info "loop_guard cleanup done"
    exit 1
  fi

  info "loop_guard exiting cleanly"
  info "loop_guard cleanup done"
}
main "${1:-check}"
