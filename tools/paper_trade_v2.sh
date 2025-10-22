#!/bin/bash
# Log V2 signals without executing

while true; do
    echo "$(date) - Checking V2 strategy..."
    python3 ~/bot-a/tools/strategy_v2_hybrid.py >> ~/bot-a/logs/v2_paper.log
    sleep 3600  # Every hour
done
