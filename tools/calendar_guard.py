#!/usr/bin/env python3
"""
BotA Calendar Guard v3
======================
Uses Global Economic Calendar API (RapidAPI / serifcolakel) — free tier.
Blocks signals around HIGH/MEDIUM impact events for relevant currencies.
Fails open if API unavailable — trading continues unaffected.

Exit codes:
  0 = safe to trade
  1 = hard block (HIGH/MEDIUM impact event within window)

Usage:
  python3 tools/calendar_guard.py --pair EURUSD
  python3 tools/calendar_guard.py --pair EURUSD --json

Integration in signal_watcher_pro.sh:
  Already wired via news_filter_real.py — this script is standalone/optional.
"""

from __future__ import annotations
import os, sys, json, urllib.request, urllib.parse, datetime, argparse

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_CALENDAR_KEY", "")
RAPIDAPI_HOST = "global-economic-calendar-api-multi-language.p.rapidapi.com"
RAPIDAPI_URL  = f"https://{RAPIDAPI_HOST}/api/v1/economic-calendar/events"

PAIR_CURRENCIES = {
    "EURUSD": ("USD", "EU"),
    "GBPUSD": ("USD", "GB"),
    "USDJPY": ("USD", "JP"),
    "AUDUSD": ("USD", "AU"),
    "USDCAD": ("USD", "CA"),
    "USDCHF": ("USD", "CH"),
    "EURJPY": ("EU", "JP"),
    "GBPJPY": ("GB", "JP"),
}

# Currency code mapping from country_code to currency
COUNTRY_TO_CURRENCY = {
    "US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY",
    "AU": "AUD", "CA": "CAD", "CH": "CHF", "NZ": "NZD",
}

HARD_BLOCK = {
    "HIGH":   {"before": 30, "after": 60},
    "MEDIUM": {"before": 15, "after": 30},
}

HIGH_KEYWORDS = [
    "non-farm", "nfp", "payroll", "fomc", "federal reserve",
    "fed interest rate", "interest rate decision",
    "cpi", "inflation", "gdp",
    "bank of england", "boe", "ecb rate",
    "unemployment",
]


def fetch_events(country_codes: list) -> list:
    if not RAPIDAPI_KEY:
        return []
    try:
        params = urllib.parse.urlencode({
            "country_codes": ",".join(country_codes),
            "language": "en"
        })
        req = urllib.request.Request(
            f"{RAPIDAPI_URL}?{params}",
            headers={
                "Content-Type": "application/json",
                "x-rapidapi-host": RAPIDAPI_HOST,
                "x-rapidapi-key": RAPIDAPI_KEY,
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return data.get("data", [])
    except Exception as e:
        sys.stderr.write(f"[CALENDAR] fetch error: {e}\n")
        return []


def check_events(events: list, currencies: tuple, now_ts: float) -> dict:
    result = {
        "block": False,
        "soft_warning": False,
        "penalty_points": 0,
        "reason": "clear",
        "nearest_event": "",
        "minutes_away": 9999.0,
    }

    pair_currencies_set = set(currencies)

    for event in events:
        currency = event.get("currency", "")
        # Also check via country_code
        country_code = event.get("country_code", "")
        mapped_currency = COUNTRY_TO_CURRENCY.get(country_code, "")

        if currency not in pair_currencies_set and mapped_currency not in pair_currencies_set:
            continue

        importance = event.get("importance", "LOW")
        occ_time   = event.get("occurrence_time", "")
        name       = event.get("localization", {}).get("long_name", "")
        name_lower = name.lower()

        # Parse occurrence time
        try:
            dt = datetime.datetime.strptime(occ_time[:19], "%Y-%m-%dT%H:%M:%S")
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            ts = dt.timestamp()
        except Exception:
            continue

        minutes_away = (ts - now_ts) / 60.0

        # Track nearest
        if abs(minutes_away) < abs(result["minutes_away"]):
            result["minutes_away"] = round(minutes_away, 1)
            result["nearest_event"] = f"{currency} '{name}' ({minutes_away:+.0f}m)"

        # Keyword override → HIGH
        is_high_kw = any(kw in name_lower for kw in HIGH_KEYWORDS)
        effective = "HIGH" if is_high_kw else importance

        if effective in HARD_BLOCK:
            rules = HARD_BLOCK[effective]
            in_before = -rules["before"] <= minutes_away <= 0
            in_after  = 0 < minutes_away <= rules["after"]
            if in_before or in_after:
                direction = "before" if minutes_away < 0 else "after"
                result["block"] = True
                result["reason"] = (
                    f"{effective} {currency} '{name}' "
                    f"{abs(minutes_away):.0f}min {direction}"
                )
                return result

    return result


def main():
    ap = argparse.ArgumentParser(description="BotA Calendar Guard v3")
    ap.add_argument("--pair", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pair = args.pair.upper().replace("/", "").replace("_", "")
    country_codes = list(PAIR_CURRENCIES.get(pair, ()))

    if not country_codes:
        out = {"block": False, "reason": f"unknown_pair_{pair}", "pair": pair}
        if args.json: print(json.dumps(out))
        sys.exit(0)

    if not RAPIDAPI_KEY:
        out = {"block": False, "reason": "no_api_key_fail_open", "pair": pair}
        if args.json: print(json.dumps(out))
        sys.exit(0)

    # Map country codes to currency codes for matching
    currencies = tuple(
        COUNTRY_TO_CURRENCY.get(cc, cc) for cc in country_codes
    )

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    events = fetch_events(country_codes)
    result = check_events(events, currencies, now_ts)

    result["pair"] = pair
    result["events_checked"] = len(events)
    result["checked_at"] = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["block"]:
            print(f"BLOCK: {result['reason']}")
        elif result["soft_warning"]:
            print(f"WARN: {result['reason']}")
        else:
            near = result["nearest_event"] or "none"
            print(f"CLEAR: {pair} safe ({result['events_checked']} events, nearest: {near})")

    sys.exit(1 if result["block"] else 0)


if __name__ == "__main__":
    main()

