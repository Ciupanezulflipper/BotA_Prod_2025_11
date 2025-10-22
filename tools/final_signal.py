#!/usr/bin/env python3
# tools/final_signal.py
#
# Build and (optionally) send ONE combined trading card.
# Works with tools.card_templates and tools.telegramalert.
# Defaults are conservative; pass CLI flags to override.

import argparse
import datetime as dt
import os
from typing import Dict, Any

# Local helpers
from tools.card_templates import compose_card
from tools.telegramalert import send_card

UTC = dt.timezone.utc


def fmt_price(x: float, pip: float) -> str:
    """
    Format price based on instrument pip size.
    - FX (pip < 0.01) -> 5 decimals
    - Metals/indices (pip >= 0.01) -> 2 decimals
    """
    if x is None:
        return "–"
    return f"{x:.5f}" if pip < 0.01 else f"{x:.2f}"


def guess_pip(symbol: str) -> float:
    s = symbol.upper()
    if "XAU" in s or "XAG" in s or s.endswith("USD-GOLD"):
        return 0.01
    # default FX pip
    return 0.0001


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compose and optionally send ONE combined signal card."
    )
    p.add_argument("--symbol", required=True, help="Instrument symbol (e.g., EURUSD, XAUUSD)")
    p.add_argument("--decision", default="HOLD", choices=["BUY", "SELL", "HOLD"], help="Final trade decision")
    p.add_argument("--news-score", type=float, default=0.0, help="0..10 impact score from news module")
    p.add_argument("--tech-bucket", default="HOLD", choices=["BUY", "SELL", "HOLD"], help="Tech verdict bucket")
    p.add_argument("--tech-score", type=int, default=0, help="Signed tech score contribution (e.g., +2, -1)")
    p.add_argument("--confidence", type=float, default=0.0, help="0..10 overall confidence")
    p.add_argument("--entry", type=float, default=None, help="Entry price")
    p.add_argument("--tp", type=float, default=None, help="Take profit")
    p.add_argument("--sl", type=float, default=None, help="Stop loss")
    p.add_argument("--risk", default="Medium", help="Risk label (Low/Medium/High)")
    p.add_argument("--timeframe", default="4h", help="Primary timeframe label")
    p.add_argument("--why", default="", help="Short rationale text")
    p.add_argument("--send", action="store_true", help="Send to Telegram (otherwise just print)")
    p.add_argument("--dry", action="store_true", help="Force print only (overrides --send)")
    return p.parse_args()


def build_payload(ns: argparse.Namespace) -> Dict[str, Any]:
    now_utc = dt.datetime.now(UTC).strftime("UTC %H:%M")

    pip = guess_pip(ns.symbol)

    payload: Dict[str, Any] = dict(
        symbol=ns.symbol.upper(),
        decision=ns.decision.upper(),
        news_score=clamp(ns.news_score, 0.0, 10.0),
        tech_bucket=ns.tech_bucket.upper(),
        tech_score=int(ns.tech_score),
        why=ns.why or "—",
        confidence=clamp(ns.confidence, 0.0, 10.0),
        entry=fmt_price(ns.entry, pip) if ns.entry is not None else "—",
        tp=fmt_price(ns.tp, pip) if ns.tp is not None else "—",
        sl=fmt_price(ns.sl, pip) if ns.sl is not None else "—",
        risk=ns.risk,
        timeframe=ns.timeframe,
        time_now=now_utc,
    )
    return payload


def main() -> None:
    ns = parse_args()
    payload = build_payload(ns)

    # Compose the final card once; same template used everywhere.
    card = compose_card(**payload)

    # Always print (so you can see the exact card locally)
    print(card)

    if ns.dry or not ns.send:
        return

    ok = send_card(payload)
    if not ok:
        # telegramalert already prints fallback text on failure, but make it explicit
        print("[final_signal] send failed (telegramalert reported failure)")
    else:
        print("[final_signal] sent")


if __name__ == "__main__":
    main()
