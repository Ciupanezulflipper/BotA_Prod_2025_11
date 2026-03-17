#!/usr/bin/env python3
"""
BotA Calendar Guard
===================
Checks OANDA ForexLabs calendar for upcoming high-impact events.
Returns exit code 0 = safe to trade, 1 = blocked by news event.
Also prints a JSON result for integration with signal_watcher_pro.sh.

Usage:
  python3 tools/calendar_guard.py --pair EURUSD
  python3 tools/calendar_guard.py --pair GBPUSD --window 30

Exit codes:
  0 = safe to trade
  1 = hard block (high/medium impact event within window)
  2 = soft warning (low impact event nearby, score penalty applies)

Environment:
  OANDA_API_TOKEN — required
  OANDA_API_URL   — optional, defaults to practice

Integration with signal_watcher_pro.sh:
  Add before signal generation:
    if ! python3 tools/calendar_guard.py --pair "${PAIR}" >/dev/null 2>&1; then
      log "CALENDAR BLOCK: ${PAIR} — skipping signal"
      continue
    fi
"""

from __future__ import annotations
import os, sys, json, urllib.request, datetime, argparse

OANDA_TOKEN = os.environ.get("OANDA_API_TOKEN", "")
OANDA_URL   = os.environ.get("OANDA_API_URL", "https://api-fxpractice.oanda.com").rstrip("/")

# Currency mapping for pairs
PAIR_CURRENCIES = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "AUDUSD": ("AUD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "USDCHF": ("USD", "CHF"),
    "EURJPY": ("EUR", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
}

# Hard block windows (minutes before/after event)
HARD_BLOCK_RULES = {
    3: {"before": 30, "after": 60},   # HIGH impact: 30min before, 60min after
    2: {"before": 15, "after": 30},   # MEDIUM impact: 15min before, 30min after
}

# Soft warning window for low impact
SOFT_WARNING_RULES = {
    1: {"before": 10, "after": 10},   # LOW impact: 10min before/after
}

# Score penalty for soft warnings (applied to signal score)
SOFT_PENALTY_POINTS = -5

# High-impact keywords that always trigger hard block regardless of impact level
HIGH_IMPACT_KEYWORDS = [
    "nfp", "non-farm", "non farm", "payroll",
    "fomc", "federal reserve", "fed rate",
    "cpi", "inflation",
    "gdp",
    "boe rate", "bank of england",
    "ecb rate", "european central bank",
]


def fetch_calendar(pair_currencies: tuple, period_hours: int = 24) -> list:
    """Fetch OANDA ForexLabs calendar events for the next period_hours."""
    if not OANDA_TOKEN:
        return []

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        # Fetch events for next 24 hours
        period = period_hours * 3600
        url = f"{OANDA_URL}/labs/v1/calendar?period={period}"

        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {OANDA_TOKEN}",
            "Content-Type": "application/json"
        })

        with urllib.request.urlopen(req, timeout=10) as r:
            events = json.loads(r.read())

        if not isinstance(events, list):
            return []

        # Filter to relevant currencies only
        base_cur, quote_cur = pair_currencies
        relevant = []
        for event in events:
            currency = event.get("currency", "")
            if currency in (base_cur, quote_cur):
                relevant.append(event)

        return relevant

    except Exception as e:
        # Fail open — if calendar unavailable, don't block trading
        sys.stderr.write(f"[CALENDAR] fetch error: {e}\n")
        return []


def check_events(events: list, now_ts: float) -> dict:
    """
    Check events against blocking rules.
    Returns: {
        "block": bool,
        "soft_warning": bool,
        "penalty_points": int,
        "reason": str,
        "nearest_event": str,
        "minutes_away": float
    }
    """
    result = {
        "block": False,
        "soft_warning": False,
        "penalty_points": 0,
        "reason": "clear",
        "nearest_event": "",
        "minutes_away": 9999.0
    }

    for event in events:
        ts = event.get("timestamp", 0)
        impact = int(event.get("impact", 1))
        title = str(event.get("title", "")).lower()
        currency = event.get("currency", "")

        minutes_away = (ts - now_ts) / 60.0  # Negative = already happened

        # Update nearest event tracking
        if abs(minutes_away) < abs(result["minutes_away"]):
            result["minutes_away"] = round(minutes_away, 1)
            result["nearest_event"] = f"{currency} {event.get('title', '')} ({minutes_away:+.0f}m)"

        # Check for high-impact keywords — override impact level to 3
        is_high_keyword = any(kw in title for kw in HIGH_IMPACT_KEYWORDS)
        effective_impact = 3 if is_high_keyword else impact

        # Hard block check
        if effective_impact in HARD_BLOCK_RULES:
            rules = HARD_BLOCK_RULES[effective_impact]
            in_before = -rules["before"] <= minutes_away <= 0
            in_after  = 0 < minutes_away <= rules["after"]

            if in_before or in_after:
                direction = "before" if minutes_away < 0 else "after"
                result["block"] = True
                result["reason"] = (
                    f"IMPACT{effective_impact} {currency} '{event.get('title','')}' "
                    f"{abs(minutes_away):.0f}min {direction}"
                )
                return result  # Hard block — return immediately

        # Soft warning check
        elif effective_impact in SOFT_WARNING_RULES:
            rules = SOFT_WARNING_RULES[effective_impact]
            in_window = -rules["before"] <= minutes_away <= rules["after"]
            if in_window:
                result["soft_warning"] = True
                result["penalty_points"] = SOFT_PENALTY_POINTS
                result["reason"] = (
                    f"LOW_IMPACT {currency} '{event.get('title','')}' "
                    f"{abs(minutes_away):.0f}min away"
                )

    return result


def main():
    ap = argparse.ArgumentParser(description="BotA Calendar Guard")
    ap.add_argument("--pair", required=True, help="e.g. EURUSD")
    ap.add_argument("--window", type=int, default=24, help="Hours to look ahead (default 24)")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of plain text")
    args = ap.parse_args()

    pair = args.pair.upper().replace("/", "").replace("_", "")
    currencies = PAIR_CURRENCIES.get(pair)

    if not currencies:
        output = {"block": False, "reason": f"unknown pair {pair}", "soft_warning": False}
        if args.json:
            print(json.dumps(output))
        sys.exit(0)

    if not OANDA_TOKEN:
        output = {"block": False, "reason": "no_token_fail_open", "soft_warning": False}
        if args.json:
            print(json.dumps(output))
        sys.exit(0)

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    events = fetch_calendar(currencies, period_hours=args.window)
    result = check_events(events, now_ts)

    result["pair"] = pair
    result["events_checked"] = len(events)
    result["checked_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["block"]:
            print(f"BLOCK: {result['reason']}")
        elif result["soft_warning"]:
            print(f"WARN: {result['reason']} (penalty: {result['penalty_points']} pts)")
        else:
            print(f"CLEAR: {pair} safe to trade ({len(events)} events checked)")

    # Exit codes: 0=clear/soft, 1=hard block
    sys.exit(1 if result["block"] else 0)


if __name__ == "__main__":
    main()

