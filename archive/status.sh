#!/usr/bin/env bash
set -euo pipefail
echo "== PIDs =="; cat ~/bot-a/logs/runner_full_institutional.pid ~/bot-a/logs/runner_full_aggressive.pid 2>/dev/null || true
echo "== Tails =="
tail -n 2 ~/bot-a/logs/runner_full_institutional.log 2>/dev/null || true
tail -n 2 ~/bot-a/logs/runner_full_aggressive.log 2>/dev/null || true
