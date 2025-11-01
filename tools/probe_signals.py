#!/usr/bin/env python3
"""
probe_signals.py — call status_pretty.py and extract coarse H1 signals.
Outputs JSON to stdout:
  {"EURUSD":{"dir":"BUY|SELL|NEUTRAL","rsi":61,"m5":"NA"} , ...}
Notes:
- Simple parser against the formatted text produced by tools/status_pretty.py advanced
- M5 not present in that output; we set "NA" for now (placeholder)
"""
import json, os, re, subprocess, sys

ROOT = os.path.expanduser("~/BotA")
status_script = os.path.join(ROOT, "tools", "status_pretty.py")

def run_status():
    try:
        out = subprocess.check_output(
            ["python3", status_script, "advanced"], stderr=subprocess.STDOUT, text=True, timeout=25
        )
        return out
    except Exception as e:
        return ""

text = run_status()

pairs = ["EURUSD","GBPUSD"]
data = {p: {"dir":"NEUTRAL","rsi":None,"m5":"NA"} for p in pairs}

# Normalize lines
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

# Patterns seen in your screenshots:
# "EUR/USD H1 — 2025-10-28 09:00 UTC"
# Next lines include either "BUY" or "SELL" and "RSI 61"
pair_line = re.compile(r"^([A-Z]{3}/[A-Z]{3})\s+H1\b")
rsx_line  = re.compile(r"RSI\s+(\d+)")
buy_kw, sell_kw = "BUY", "SELL"

cur = None
for ln in lines:
    m = pair_line.search(ln)
    if m:
        cur = m.group(1).replace("/","")
        if cur not in data:
            data[cur] = {"dir":"NEUTRAL","rsi":None,"m5":"NA"}
        continue
    if cur:
        if buy_kw in ln and "Trend" in ln or (ln.startswith("BUY") or " BUY " in ln):
            data[cur]["dir"] = "BUY"
        if sell_kw in ln and "Trend" in ln or (ln.startswith("SELL") or " SELL " in ln):
            data[cur]["dir"] = "SELL"
        m2 = rsx_line.search(ln)
        if m2:
            try:
                data[cur]["rsi"] = int(m2.group(1))
            except:
                pass

print(json.dumps(data))
