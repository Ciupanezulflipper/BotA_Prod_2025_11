#!/usr/bin/env python3
"""
trade_summary.py - Live profitability report from accuracy.csv
Columns: alert_ts,pair,dir,window_min,result,pips,data_age_sec,source,confidence,evaluated_at
"""
import csv, os, sys
from collections import defaultdict

CSV = os.path.expanduser("~/BotA/logs/accuracy.csv")
if not os.path.exists(CSV):
    print("accuracy.csv not found"); sys.exit(1)

pairs = defaultdict(lambda: {"win":0,"loss":0,"neutral":0,"pips":0.0,"total":0})
overall = {"win":0,"loss":0,"neutral":0,"pips":0.0,"total":0}

with open(CSV) as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = (row.get("result","") or "").upper()
        pair = row.get("pair","ALL")
        try: pips = float(row.get("pips","0") or 0)
        except: pips = 0.0
        for d in [pairs[pair], overall]:
            d["total"] += 1
            d["pips"] += pips
            if "WIN" in result: d["win"] += 1
            elif "LOSS" in result: d["loss"] += 1
            elif result not in ("","PENDING","STALE","PENDING: STALE","PENDING:STALE"):
                d["neutral"] += 1

print(f"{'PAIR':<12} {'TOTAL':>6} {'WIN':>5} {'LOSS':>5} {'NEUT':>5} {'WIN%':>6} {'PIPS':>8}")
print("-" * 55)
for pair, d in sorted(pairs.items()):
    traded = d["win"] + d["loss"]
    wp = f"{100*d['win']/traded:.0f}%" if traded else "n/a"
    print(f"{pair:<12} {d['total']:>6} {d['win']:>5} {d['loss']:>5} {d['neutral']:>5} {wp:>6} {d['pips']:>8.1f}")
print("-" * 55)
d = overall
traded = d["win"] + d["loss"]
wp = f"{100*d['win']/traded:.0f}%" if traded else "n/a"
print(f"{'TOTAL':<12} {d['total']:>6} {d['win']:>5} {d['loss']:>5} {d['neutral']:>5} {wp:>6} {d['pips']:>8.1f}")
