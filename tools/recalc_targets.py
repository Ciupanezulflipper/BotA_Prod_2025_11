#!/usr/bin/env python3
import os, sys, pandas as pd
from datetime import datetime

IN = sys.argv[1] if len(sys.argv)>1 else "signals_v2.csv"
OUT = sys.argv[2] if len(sys.argv)>2 else "signals_v2_recalc.csv"

SL_MULT  = float(os.getenv("ATR_SL_MULT",  "1.5"))
TP1_MULT = float(os.getenv("ATR_TP1_MULT", "1.2"))  # try tighter TP1
TP2_MULT = float(os.getenv("ATR_TP2_MULT", "2.4"))
TP3_FACTOR = 1.5  # TP3 = TP2_MULT * 1.5

def recalc_row(r):
    try:
        act = str(r["action"]).upper()
        e   = float(r["entry_price"])
        atr = float(r["atr"]) if str(r["atr"]).lower()!="n/a" else None
        if act not in ("BUY","SELL") or atr is None or atr<=0:
            return r
        if act=="BUY":
            r["stop_loss"] = f"{e - SL_MULT*atr/10000:.5f}"
            r["tp1"]      = f"{e + TP1_MULT*atr/10000:.5f}"
            r["tp2"]      = f"{e + TP2_MULT*atr/10000:.5f}"
            r["tp3"]      = f"{e + (TP2_MULT*TP3_FACTOR)*atr/10000:.5f}"
        else:
            r["stop_loss"] = f"{e + SL_MULT*atr/10000:.5f}"
            r["tp1"]      = f"{e - TP1_MULT*atr/10000:.5f}"
            r["tp2"]      = f"{e - TP2_MULT*atr/10000:.5f}"
            r["tp3"]      = f"{e - (TP2_MULT*TP3_FACTOR)*atr/10000:.5f}"
    except:
        pass
    return r

df = pd.read_csv(IN)
need = ["timestamp","pair","timeframe","action","entry_price","stop_loss","tp1","tp2","tp3","atr"]
for c in need:
    if c not in df.columns:
        raise SystemExit(f"Missing column {c} in {IN}")

df = df.apply(recalc_row, axis=1)
df.to_csv(OUT, index=False)
print(f"✓ Wrote recalculated targets to {OUT}")
