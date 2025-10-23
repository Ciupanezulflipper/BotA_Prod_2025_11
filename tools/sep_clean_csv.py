import csv, os, hashlib, datetime as dt
src = os.path.expanduser('~/BotA/trades.csv')
dst = os.path.expanduser('~/BotA/trades.cleaned.csv')
if not os.path.exists(src):
    print("No trades.csv yet"); raise SystemExit

seen=set(); out=[]
with open(src) as f:
    for r in csv.reader(f):
        if len(r)<8: 
            out.append(r); continue
        ts,pair,side,entry,tp,sl,atr,weighted = r[:8]
        # key rounded to minute + price granularity to catch rebroadcasts
        try:
            tmin = dt.datetime.fromisoformat(ts.replace('Z','+00:00')).replace(second=0, microsecond=0).isoformat()
        except Exception:
            tmin = ts
        key = f"{tmin}|{pair}|{side}|{entry}|{tp}|{sl}"
        h = hashlib.sha1(key.encode()).hexdigest()[:12]
        if h in seen: 
            continue
        seen.add(h)
        out.append(r)

with open(dst,'w',newline='') as f:
    csv.writer(f).writerows(out)

print(f"Wrote {len(out)} rows -> {dst}")
