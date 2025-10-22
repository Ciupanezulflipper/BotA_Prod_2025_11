#!/usr/bin/env bash
set -euo pipefail
mkdir -p ~/bot-a/logs
# Institutional
( set -a; . ~/.env.institutional; set +a; \
  nohup python3 ~/bot-a/tools/runner_full.py \
  >> ~/bot-a/logs/runner_full_institutional.log 2>&1 & echo $! > ~/bot-a/logs/runner_full_institutional.pid )
# Aggressive
( set -a; . ~/.env.aggressive; set +a; \
  nohup python3 ~/bot-a/tools/runner_full.py \
  >> ~/bot-a/logs/runner_full_aggressive.log 2>&1 & echo $! > ~/bot-a/logs/runner_full_aggressive.pid )
echo "Started both runners."
