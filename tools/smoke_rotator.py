# ~/bot-a/tools/smoke_rotator.py
import pandas as pd
from tools.data_rotator import get_ohlc_rotating

for sym in ["EURUSD", "XAUUSD"]:
    df, prov = get_ohlc_rotating(sym, "1h", limit=20)
    print(f"\n=== {sym} via {prov} ===")
    print(df.tail(3))
