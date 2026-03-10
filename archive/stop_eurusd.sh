#!/usr/bin/env bash
set -euo pipefail
pkill -f "bot-a/tools/auto_eurusd.sh" || true
echo "Stopped auto EURUSD (if running)."
