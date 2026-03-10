#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# load env
export $(grep -v '^\s*#' ~/.env | xargs)

PAIR="${1:-EURUSD}"
TF="${2:-M15}"
SCORE="${SCORE:-0.95}"
CONF="${CONF:-9.0}"
REASON="${REASON:-test-send}"

PAIR="$PAIR" TF="$TF" SCORE="$SCORE" CONF="$CONF" REASON="$REASON" \
  python3 "$HOME/bot-a/tools/send_test_signal.py"
