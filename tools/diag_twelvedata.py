#!/usr/bin/env python3
import os, sys, json, urllib.request, urllib.parse

def fetch(sym, interval, key):
    url="https://api.twelvedata.com/time_series"
    q={"symbol":sym,"interval":interval,"outputsize":"5","timezone":"UTC","format":"JSON","apikey":key}
    with urllib.request.urlopen(url+"?"+urllib.parse.urlencode(q), timeout=12) as r:
        txt=r.read().decode("utf-8","replace")
    try:
        j=json.loads(txt)
    except Exception:
        print("Non-JSON:", txt[:400]); return
    print(f"--- {sym} {interval} ---")
    print("keys:", list(j.keys()))
    if isinstance(j, dict) and j.get("status")=="error":
        print("status:error message:", j.get("message"))
    vals=j.get("values")
    if isinstance(vals, list):
        print("values_count:", len(vals))
        print("sample:", json.dumps(vals[:2], indent=2))
    else:
        print("values missing or not a list:", type(vals).__name__)

def main():
    if len(sys.argv)<2:
        print("usage: diag_twelvedata.py EURUSD"); sys.exit(2)
    raw=sys.argv[1].upper()
    key=os.getenv("TWELVEDATA_API_KEY","")
    if not key:
        print("TWELVEDATA_API_KEY missing"); sys.exit(2)
    cands=[raw]
    if len(raw)==6 and raw.isalpha(): cands.append(raw[:3]+"/"+raw[3:])
    if "/" in raw: cands.append(raw.replace("/",""))
    seen=set()
    for s in cands:
        if s in seen: continue
        seen.add(s)
        for tf in ("1h","4h","1day"):
            try:
                fetch(s, tf, key)
            except Exception as e:
                print(f"{s} {tf} error:", e)
        print()
if __name__=="__main__": main()
