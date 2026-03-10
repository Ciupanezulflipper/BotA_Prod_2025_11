#!/usr/bin/env python3
# tz_helper.py — resolve display timezone (phone tz by default; override via env)
import os, subprocess
from zoneinfo import ZoneInfo

def _read_android_tz():
    # Try Android system prop
    try:
        out = subprocess.check_output(["getprop", "persist.sys.timezone"], timeout=1).decode().strip()
        if out:
            return out
    except Exception:
        pass
    # Try /etc/timezone if present
    for p in ("/etc/timezone",):
        try:
            with open(p,"r") as f:
                tz = f.read().strip()
                if tz:
                    return tz
        except Exception:
            pass
    return None

def resolve_display_zone():
    # 1) explicit override
    tz = os.environ.get("LOCAL_TZ")
    if tz:
        try:
            return ZoneInfo(tz)
        except Exception:
            pass
    # 2) use phone tz unless disabled
    use_phone = os.environ.get("USE_PHONE_TZ", "1") not in ("0","false","False","no","NO")
    if use_phone:
        tzname = _read_android_tz()
        if tzname:
            try:
                return ZoneInfo(tzname)
            except Exception:
                pass
    # 3) fallback
    return ZoneInfo("UTC")
