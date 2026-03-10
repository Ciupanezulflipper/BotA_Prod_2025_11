#!/usr/bin/env python3
import os, sys, json, time
HOME = os.path.expanduser("~")
CACHE = os.path.join(HOME, "BotA", "cache")

def load(pair, tf):
    p = os.path.join(CACHE, f"{pair}_{tf}.json")
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except: return None

def get_ts_seconds(x):
    # accept epoch seconds or ISO8601 Z
    if x is None: return None
    if isinstance(x, (int, float)): return int(x)
    try:
        # 2025-10-23T12:49:11Z -> epoch
        import datetime as dt
        return int(dt.datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())
    except Exception:
        return None

def main():
    if len(sys.argv) < 2:
        print("usage: time_sync_check.py PAIR", file=sys.stderr); sys.exit(2)
    pair = sys.argv[1].upper()
    out = {}
    for tf in ("H1","H4","D1"):
        d = load(pair, tf)
        out[tf] = get_ts_seconds(d.get("ts") if d else None)
    if None in out.values():
        print(f"[sync] ❌ missing ts: {out}")
        sys.exit(3)
    skew = max(out.values()) - min(out.values())
    print(f"[sync] {pair} H1/H4/D1 ts={out} skew={skew}s")
    if skew > 3600:
        print(f"[sync] ❌ Timeframe skew > 1h ({skew}s) — block run")
        sys.exit(4)
    print("[sync] ✅ OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
