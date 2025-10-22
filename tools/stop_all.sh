#!/usr/bin/env bash
set -euo pipefail
kill $(cat ~/bot-a/logs/runner_full_institutional.pid) 2>/dev/null || true
kill $(cat ~/bot-a/logs/runner_full_aggressive.pid) 2>/dev/null || true
echo "Stop signals sent."
