from __future__ import annotations
from datetime import datetime, timezone, timedelta
import os, json
from urllib.request import urlopen
from urllib.parse import urlencode
from typing import Tuple

UTC = timezone.utc

# Basic symbol → currency map (extend as needed)
PAIR_TO_CCY = {
    "EURUSD": ["EUR","USD"],
    "GBPUSD": ["GBP","USD"],
    "USDJPY": ["USD","JPY"],
    "XAUUSD": ["USD"],  # gold => USD-sensitive
}

def _needs_block(imp: str) -> bool:
    return imp.lower() in {"high","red","3","3_high"}

def news_risk_gate(pair: str, now: datetime | None = None, window_min: int = 60) -> Tuple[bool, str]:
    """
    Returns (ok_to_trade, note). ok_to_trade=False means block (red news).
    Tries Finnhub economic calendar if FINNHUB_API_KEY set. Falls back to PASS.
    """
    if os.getenv("NEWS_BLOCK_ENABLED","true").lower() != "true":
        return True, "news_filter_disabled"
    key = os.getenv("FINNHUB_API_KEY","")
    if not key:
        return True, "no_calendar_api"

    now = (now or datetime.now(UTC)).astimezone(UTC)
    start = (now - timedelta(minutes=window_min)).strftime("%Y-%m-%d")
    end   = (now + timedelta(minutes=window_min)).strftime("%Y-%m-%d")

    try:
        url = "https://finnhub.io/api/v1/calendar/economic?"+ urlencode({"from":start,"to":end,"token":key})
        with urlopen(url, timeout=int(os.getenv("HTTP_TIMEOUT_SEC","8"))) as r:
            data = json.loads(r.read().decode("utf-8"))
        events = data.get("economicCalendar", [])
        watch_ccy = PAIR_TO_CCY.get(pair.upper(), [])
        for ev in events:
            cc = (ev.get("currency") or "").upper()
            imp = str(ev.get("impact") or "").lower()
            # event time is date-only from Finnhub; approximate to whole day → we still block if currencies match.
            if cc in watch_ccy and _needs_block(imp):
                return False, f"red_news_{cc}"
        return True, "no_red_news"
    except Exception:
        # On any failure, do not hard-block; just warn via note
        return True, "calendar_unavailable"
