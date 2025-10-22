#!/bin/bash
# Daily baseline tracker for first 7 days

LOG="$HOME/bot-a/logs/auto_h1.log"
REPORT="$HOME/bot-a/logs/baseline_$(date +%Y%m%d).txt"

echo "=== Day $(( ($(date +%s) - $(date -d '2025-10-16' +%s)) / 86400 + 1 )) Baseline Report ===" > "$REPORT"
echo "Date: $(date)" >> "$REPORT"
echo "" >> "$REPORT"

# Count signals
BUYS=$(grep "Action: BUY" "$LOG" | grep "$(date +%Y-%m-%d)" | wc -l)
SELLS=$(grep "Action: SELL" "$LOG" | grep "$(date +%Y-%m-%d)" | wc -l)
WAITS=$(grep "Action: WAIT" "$LOG" | grep "$(date +%Y-%m-%d)" | wc -l)

echo "Signals Today:" >> "$REPORT"
echo "  BUY:  $BUYS" >> "$REPORT"
echo "  SELL: $SELLS" >> "$REPORT"
echo "  WAIT: $WAITS" >> "$REPORT"
echo "" >> "$REPORT"

# API usage
python3 ~/bot-a/tools/api_circuit_breaker.py >> "$REPORT" 2>&1

# Risk status
echo "" >> "$REPORT"
python3 ~/bot-a/tools/risk_manager.py >> "$REPORT" 2>&1

cat "$REPORT"

# Send to Telegram
python3 ~/bot-a/tools/tg_send.py "$(cat $REPORT)"
