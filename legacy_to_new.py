#!/usr/bin/env python3
"""
legacy_to_new.py - Convert legacy signals.csv → new schema for BotA auditor
"""

import pandas as pd
from datetime import timezone
import numpy as np

inp = "signals.csv"
out = "signals_v2.csv"
DEFAULT_TF = "M15"

df = pd.read_csv(inp)
df.columns = [c.strip().lower() for c in df.columns]

keep = ["timestamp","pair","action","entry","sl","tp","rr","confidence","mode","reason"]
df = df[[c for c in keep if c in df.columns]].copy()

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
df = df.dropna(subset=["timestamp"])

for col in ["pair","action","entry"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip()
df = df[(df["pair"] != "") & (df["action"] != "") & (df["entry"] != "")]

outcols = [
    "timestamp","pair","timeframe","action","entry_price","stop_loss",
    "tp1","tp2","tp3","spread","atr","score16","score6","reason",
    "original_action","rejection_reason"
]
outdf = pd.DataFrame(columns=outcols)

outdf["timestamp"] = df["timestamp"].dt.tz_convert(timezone.utc).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
outdf["pair"] = df["pair"].str.upper()
outdf["timeframe"] = DEFAULT_TF
outdf["action"] = df["action"].str.upper().replace({"HOLD":"WAIT"})
outdf["entry_price"] = pd.to_numeric(df["entry"], errors="coerce")
outdf["stop_loss"] = pd.to_numeric(df.get("sl"), errors="coerce")
tp = pd.to_numeric(df.get("tp"), errors="coerce")
outdf["tp1"] = tp
outdf["tp2"] = np.nan
outdf["tp3"] = np.nan
outdf["spread"] = "n/a"
outdf["atr"] = "n/a"
outdf["score16"] = "n/a"
outdf["score6"] = "n/a"
outdf["reason"] = df.get("reason", "")
outdf["original_action"] = outdf["action"]
outdf["rejection_reason"] = ""

outdf = outdf.dropna(subset=["entry_price","stop_loss","tp1"])

for c in ["entry_price","stop_loss","tp1","tp2","tp3"]:
    outdf[c] = outdf[c].map(lambda x: f"{x:.5f}" if pd.notna(x) else "n/a")

outdf.to_csv(out, index=False)
print(f"✓ Wrote {len(outdf)} rows to {out}")
