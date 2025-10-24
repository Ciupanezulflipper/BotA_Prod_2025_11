#!/usr/bin/env python3
import sys, json, urllib.request, urllib.parse, time

def pull(sym, rng, interval):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    q={"range":rng, "interval":interval}
    try:
        with urllib.request.urlopen(url+"?"+urllib.parse.urlencode(q), timeout=10) as r:
            code=getattr(r, "status", 200)
            txt=r.read().decode("utf-8","replace")
    except Exception as e:
        print(rng, interval, "error:", e); return
    try:
        j=json.loads(txt)
    except Exception:
        print(rng, interval, "non-JSON:", txt[:300]); return
    res=(j.get("chart",{}).get("result") or [None])[0]
    if not res:
        print(rng, interval, "no result: keys=", list(j.keys())); return
    closes=(res.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
    pts=len([c for c in closes if c is not None])
    print(rng, interval, "points:", pts)

def main():
    if len(sys.argv)<2:
        print("usage: diag_yahoo.py EURUSD=X"); sys.exit(2)
    ysym=sys.argv[1]
    for rng,interval in [("5d","60m"),("1mo","60m"),("3mo","60m"),("3mo","1d"),("6mo","1d")]:
        pull(ysym, rng, interval); time.sleep(0.4)
if __name__=="__main__": main()
