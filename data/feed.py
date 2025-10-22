# data/feed.py — source-agnostic OHLCV feed
# Provides a single function: get_ohlcv(symbol, tf="5min", limit=300)
# Backend can be: "mock" (default), "csv", or "none" (returns []).

import os, csv, math, time, random

def _normalize_symbol(sym:str)->str:
    s = sym.replace("/", "").upper()
    return s

# ---------- MOCK FEED (deterministic) ----------
# Generates a synthetic but realistic OHLCV series driven by sin waves + noise.
def _mock_ohlcv(symbol:str, tf:str="5min", limit:int=300):
    rnd = random.Random(_normalize_symbol(symbol) + "|" + tf)
    step = 1 if tf.endswith("min") else 12
    base_t = int(time.time()//60)*60
    period = 240  # 240 bars cycle
    px0 = 1.1000 if symbol.startswith(("EURUSD","EUR/")) else 150.0

    rows = []
    for i in range(limit, 0, -1):
        t = base_t - i*step*60
        phase = (i % period)/period
        drift = (i/limit)*0.002*(1 if symbol.endswith("USD") else -1)
        wave = 0.0025*math.sin(2*math.pi*phase) + 0.0015*math.sin(6*math.pi*phase)
        noise = rnd.uniform(-0.0006, 0.0006) if px0 < 10 else rnd.uniform(-0.2, 0.2)
        close = px0*(1 + wave + drift) if px0>10 else px0 + wave + drift
        close = close + noise
        # small OHLC body around close
        high = close + (abs(noise)*1.2)
        low  = close - (abs(noise)*1.2)
        open_ = (high+low)/2
        vol = int( rnd.uniform(50, 300) )
        rows.append({"t": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t)),
                     "o": float(open_), "h": float(high), "l": float(low),
                     "c": float(close), "v": vol})
    return rows

# ---------- CSV FEED ----------
# Looks for ./data/csv/<SYMBOL>_<TF>.csv with columns: t,o,h,l,c,v
def _csv_ohlcv(symbol:str, tf:str="5min", limit:int=300):
    sym = _normalize_symbol(symbol)
    path = os.path.join(os.path.dirname(__file__), "csv", f"{sym}_{tf}.csv")
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for it in r:
            rows.append({"t": it["t"], "o": float(it["o"]), "h": float(it["h"]),
                         "l": float(it["l"]), "c": float(it["c"]), "v": float(it.get("v",0))})
    return rows[-limit:]

# ---------- PUBLIC API ----------
def get_ohlcv(symbol:str, tf:str="5min", limit:int=300):
    backend = (os.getenv("DATA_BACKEND") or "mock").strip().lower()
    if backend == "csv":
        rows = _csv_ohlcv(symbol, tf, limit)
        if rows: return rows
        # fallback to mock if csv missing
        return _mock_ohlcv(symbol, tf, limit)
    elif backend == "mock":
        return _mock_ohlcv(symbol, tf, limit)
    return []  # "none"

