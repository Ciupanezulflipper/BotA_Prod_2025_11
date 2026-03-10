#!/usr/bin/env bash
set -euo pipefail

echo "STATUS: ok"
echo "SCOPE: Analysis only (NO code edits)."
echo "GOAL: Prove what timestamp source status_pretty SHOULD use (indicators mtimes vs Yahoo caches)."
echo

python3 - <<'PY'
import json, pathlib, time
from datetime import datetime, timezone

pairs = ["EURUSD","GBPUSD","USDJPY"]
tfs   = ["H1","M15"]

def fmt_utc(ts:int)->str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def stat_line(p: pathlib.Path):
    st = p.stat()
    mtime = int(st.st_mtime)
    now = int(time.time())
    return (mtime, now, st.st_size)

def scan_time_fields(obj, path="$"):
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            kk=str(k).lower()
            if any(s in kk for s in ["time","ts","date","updated","stamp","utc","candle","bar"]):
                out.append((f"{path}.{k}", v))
            out.extend(scan_time_fields(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i,v in enumerate(obj[:30]):
            out.extend(scan_time_fields(v, f"{path}[{i}]"))
    return out

def try_load_json(p: pathlib.Path):
    try:
        return json.loads(p.read_text("utf-8", errors="ignore"))
    except Exception:
        return None

def last_yahoo_candle_epoch(j):
    try:
        ts = j["chart"]["result"][0].get("timestamp") or []
        if isinstance(ts, list) and ts:
            return int(ts[-1])
    except Exception:
        pass
    return None

now = int(time.time())
print("now_utc:", fmt_utc(now), "| epoch", now)
print()

for pair in pairs:
    print("========================================================")
    print("PAIR:", pair)
    print("--------------------------------------------------------")

    # 1) Indicators (ACTUALLY USED by scoring_engine.sh, proven by your STEP 18A trace)
    for tf in tfs:
        ip = pathlib.Path(f"cache/indicators_{pair}_{tf}.json")
        if not ip.exists():
            print(f"[INDICATORS {tf}] MISSING:", ip)
            continue
        mtime, now2, size = stat_line(ip)
        age = now2 - mtime
        j = try_load_json(ip)
        found = scan_time_fields(j) if isinstance(j, dict) else []
        print(f"[INDICATORS {tf}] file={ip} size={size}B mtime={fmt_utc(mtime)} age_sec={age}")
        print(f"[INDICATORS {tf}] timestamp_like_fields_in_json={len(found)} (show up to 8)")
        for pth,val in found[:8]:
            print("  -", pth, "=", val)

    # 2) Yahoo chart caches (exist, but NOT used by scoring_engine.sh per your STEP 18A trace)
    yp = pathlib.Path(f"cache/{pair}_H1.json")
    if yp.exists():
        mtime, now2, size = stat_line(yp)
        age = now2 - mtime
        j = try_load_json(yp)
        lc = last_yahoo_candle_epoch(j) if isinstance(j, dict) else None
        print(f"[YAHOO H1] file={yp} size={size}B mtime={fmt_utc(mtime)} age_sec={age}")
        if lc:
            print(f"[YAHOO H1] last_candle={fmt_utc(lc)} age_sec={now2-lc}")
        else:
            print("[YAHOO H1] last_candle: NONE (unexpected)")
    else:
        print("[YAHOO H1] MISSING:", yp)

    print()

print("========================================================")
print("STEP 19 Acceptance criteria")
print("A) Indicators files show fresh mtimes (minutes old), even if JSON lacks explicit timestamps.")
print("B) Yahoo H1 files show stale mtimes/last_candle (days old), confirming they are NOT the right source for status timestamps.")
print("C) This proves status_pretty replacement should bind timestamps/freshness to indicators file mtimes (or add timestamp fields upstream).")
PY
