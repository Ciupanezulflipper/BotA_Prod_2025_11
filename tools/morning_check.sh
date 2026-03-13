#!/bin/bash
DATE=$(date +%Y-%m-%d)
echo "=============================="
echo "BotA Morning Check — $DATE"
echo "=============================="
echo ""
echo "── LAST 5 ALERTS ──"
tail -5 ~/BotA/logs/alerts.csv | awk -F',' '{print $1, $2, $3, $4, "score="$5, "blocked="$11}'
echo ""
echo "── FIRED vs BLOCKED ──"
grep "$DATE" ~/BotA/logs/alerts.csv | awk -F',' '{print $11}' | sort | uniq -c
echo ""
echo "── BLOCK REASONS ──"
grep "$DATE" ~/BotA/logs/alerts.csv | awk -F',' '$11=="true" {print $12}' | sort | uniq -c | sort -rn
echo ""
echo "── SCORE DISTRIBUTION ──"
grep "$DATE" ~/BotA/logs/alerts.csv | awk -F',' '{print $5}' | awk '{
  if($1>=85) print "HIGH(85+)"
  else if($1>=70) print "GREEN(70-84)"
  else if($1>=62) print "DEAD(62-69)"
  else print "LOW(<62)"
}' | sort | uniq -c
echo ""
echo "── STALE CANDLES ──"
grep "$DATE" ~/BotA/logs/cron.signals.log 2>/dev/null | grep STALE | wc -l
echo ""
echo "── LEDGER SUMMARY ──"
python3 ~/BotA/tools/signal_ledger.py --report | grep -A8 "OVERVIEW"
echo "=============================="
