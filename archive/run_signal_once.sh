#!/usr/bin/env bash
# Delegates LIVE to Python runner; prints mock line in DRY_RUN.
set -Eeuo pipefail

ROOT="${BOT_ROOT:-$HOME/BotA}"
TOOLS="$ROOT/tools"
PAIR="${1:-EURUSD}"

# DRY-RUN → mock one-liner (no network)
if [ "${DRY_RUN_MODE:-false}" = "true" ]; then
  echo "[run] ${PAIR} TF15 decision=WAIT score=0 weak=false provider=mock age=0.0 price=1.2345"
  exit 0
fi

# LIVE → call Python runner (single source of truth)
if [ -x "$TOOLS/run_signal_once.py" ]; then
  exec "$TOOLS/run_signal_once.py" "$PAIR"
else
  echo "[WARN] python runner missing: $TOOLS/run_signal_once.py" >&2
  exit 2
fi
