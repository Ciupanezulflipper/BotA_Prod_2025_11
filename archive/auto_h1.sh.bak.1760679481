#!/usr/bin/env bash
# Bot A — EURUSD H1 auto loop (tmux-safe, self-logging, exclusive via flock)

set -euo pipefail

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/auto_h1.log"
export LOG="$LOG_FILE"
LOCK_FILE="$LOG_DIR/auto_h1.lock"
ENV_FILE="$PROJECT_ROOT/.env.botA"

# --- Prep ---
mkdir -p "$LOG_DIR"
# Redirect ALL stdout/stderr to the log (append mode)
exec >>"$LOG_FILE" 2>&1

# --- Exclusive lock so only one loop runs ---
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] ERROR: auto_h1 already running (lock held)."
  exit 1
fi

echo "=== BotA H1 Auto-Loop START ==="
echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] PID=$$  CWD=$PROJECT_ROOT  LOG=$LOG_FILE"

# --- Env load ---
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] ERROR: Missing $ENV_FILE"
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Env loaded from .env.botA (BOT_TOKEN masked, CHAT_ID present=${CHAT_ID:+yes})"

# --- Sanity: required tools ---
for t in python3 flock; do
  command -v "$t" >/dev/null 2>&1 || { echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] ERROR: '$t' not found"; exit 1; }
done

trap 'echo "[$(date +%Y-%m-%d %H:%M:%S)] INFO: stopping auto_h1"; exit 0' SIGINT SIGTERM

cd "$PROJECT_ROOT"

echo "[$(date -u +%Y-%m-%d\ %H:%M:%S)] Entering hourly loop... (EURUSD H1)"

while true; do
  start_ts="$(date -u +'%Y-%m-%d %H:%M:%S')"
  echo ""
  echo "--- Iteration start: $start_ts ---"

  # Run strategy (no --dry-run). Keep logic untouched.
  if python3 /data/data/com.termux/files/home/bot-a/tools/runner_with_offline.py --pair EURUSD --tf H1 --bars 200; then
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] ✓ run ok"
  else
    rc=$?
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] ✗ run failed rc=$rc"
  fi

  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Sleeping 3600s"
  sleep 3600
done
