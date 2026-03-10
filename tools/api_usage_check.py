#!/usr/bin/env python3
"""
FILE: tools/api_usage_check.py
ROLE: Check Twelve Data API credit usage and warn if approaching limit.
Called by: autostatus.sh (hourly) and cron daily summary.
"""
import os, sys, json, urllib.request
from pathlib import Path

# Load .env
env = Path(__file__).parent.parent / ".env"
for line in env.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"): continue
    if "=" in line:
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

key = (os.environ.get("TWELVEDATA_API_KEY") or
       os.environ.get("TWELVE_DATA_API_KEY", "")).strip()

if not key:
    print("api_status=NO_KEY")
    sys.exit(1)

WARN_PCT = int(os.environ.get("API_WARN_PCT", "75"))
DAILY_LIMIT = int(os.environ.get("API_DAILY_LIMIT", "800"))

try:
    url = f"https://api.twelvedata.com/api_usage?apikey={key}"
    r = urllib.request.urlopen(url, timeout=10)
    data = json.loads(r.read())

    used = data.get("current_usage", 0)
    limit = data.get("plan_limit", DAILY_LIMIT)
    per_min = data.get("minutely_average", 0)
    per_min_max = data.get("plan_limit_minute", 8)
    pct = round(used / limit * 100, 1) if limit else 0

    status = "OK"
    if pct >= WARN_PCT:
        status = "WARN"
    if pct >= 90:
        status = "CRITICAL"

    print(f"api_status={status}")
    print(f"api_used={used}")
    print(f"api_limit={limit}")
    print(f"api_pct={pct}")
    print(f"api_per_min={per_min}/{per_min_max}")

except urllib.error.HTTPError as e:
    if e.code == 403:
        # Basic plan — estimate from local tracking
        print("api_status=PLAN_NO_USAGE_ENDPOINT")
        print(f"api_note=Basic 8 plan blocks /api_usage — use local tracking")
    else:
        print(f"api_status=ERROR http={e.code}")
except Exception as e:
    print(f"api_status=ERROR {e}")
