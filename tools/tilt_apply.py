#!/usr/bin/env python3
"""
tilt_apply.py
Combine recent trading signals with the latest news tilt you already collect.

Inputs (from env / sensible defaults):
  - WATCHLIST (e.g., "EURUSD,XAUUSD")
  - SCORE_MIN (fallback for combined threshold, default 35)
  - TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (optional; only used with --send)
  - OPEN_UTC/CLOSE_UTC (optional; if present, skip sending outside window)

Files it reads:
  - ~/bot-a/logs/signals-YYYYMMDD.csv   (produced by your current bot)
  - ~/bot-a/logs/news-YYYYMMDD.csv      (produced by news_sentiment.py)

What it writes:
  - ~/bot-a/logs/tilted-YYYYMMDD.csv    (enriched rows)
  - ~/bot-a/logs/state/tilt_applied-YYYYMMDD.txt  (remember processed run_ids)

Usage examples:
  PYTHONPATH="$HOME/bot-a" python ~/bot-a/tools/tilt_apply.py --since-min 30 --send
  PYTHONPATH="$HOME/bot-a" python ~/bot-a/tools/tilt_apply.py --since-min 10 --dry
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, List, Tuple

HOME = Path.home()
LOGS = HOME / "bot-a" / "logs"
STATE = LOGS / "state"
STATE.mkdir(parents=True, exist_ok=True)

UTC = timezone.utc

# ------------ small utils ------------
def utcnow() -> datetime:
    return datetime.now(tz=UTC)

def today_tag(dt: Optional[datetime]=None) -> str:
    d = (dt or utcnow()).astimezone(UTC).strftime("%Y%m%d")
    return d

def parse_bool(s: str, default=False) -> bool:
    if s is None:
        return default
    s = s.strip().lower()
    return s in ("1","true","yes","y","on")

def try_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def send_telegram(text: str) -> Tuple[bool, Optional[str]]:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat  = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return False, "missing TELEGRAM_* env"
    import urllib.parse, urllib.request
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        with urllib.request.urlopen(api, data=data, timeout=20) as r:
            body = r.read().decode("utf-8", "ignore")
            ok = '"ok":true' in body
            return ok, None if ok else body
    except Exception as e:
        return False, str(e)

def within_session(now_utc: datetime) -> bool:
    open_h  = os.getenv("OPEN_UTC")
    close_h = os.getenv("CLOSE_UTC")
    if not open_h or not close_h:
        return True
    try:
        oh = int(open_h); ch = int(close_h)
        hr = now_utc.hour
        if oh <= ch:
            return oh <= hr < ch
        # wrap over midnight
        return hr >= oh or hr < ch
    except Exception:
        return True

# ------------ data carriers ------------
@dataclass
class SignalRow:
    run_id: str
    time_utc: datetime
    symbol: str
    tf: str
    side: str          # "Bullish"/"Bearish"/"HOLD"/maybe ""
    score: float       # original score 0..100 (as you log)
    why: str

@dataclass
class NewsTilt:
    asof_utc: datetime
    symbol: str
    score: float       # typically +5 / -5 (or 0)
    bias: str          # "Bullish"/"Bearish"/"Neutral"
    why: str
    event_risk: str    # "True" / "False" as string in your CSV

# ------------ readers ------------
def load_signals(day: str, since_min: int) -> List[SignalRow]:
    path = LOGS / f"signals-{day}.csv"
    if not path.exists():
        return []
    cutoff = utcnow() - timedelta(minutes=since_min)
    out: List[SignalRow] = []
    with path.open("r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = datetime.fromisoformat(row.get("time_utc","").replace("Z","+00:00"))
            except Exception:
                continue
            if t < cutoff:
                continue
            out.append(SignalRow(
                run_id = row.get("run_id",""),
                time_utc = t,
                symbol = (row.get("symbol","") or row.get("sym","")).upper(),
                tf = row.get("tf",""),
                side = row.get("side",""),
                score = try_float(row.get("score", row.get("signal","0")), 0.0),
                why = row.get("why",""),
            ))
    return out

def load_latest_news_tilt(day: str, lookback_hours: int=6) -> Dict[str, NewsTilt]:
    """Return the most recent tilt per symbol within lookback window."""
    path = LOGS / f"news-{day}.csv"
    if not path.exists():
        return {}
    floor = utcnow() - timedelta(hours=lookback_hours)
    best: Dict[str, NewsTilt] = {}
    with path.open("r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                asof = datetime.fromisoformat(row.get("asof_utc","").replace("Z","+00:00"))
            except Exception:
                continue
            if asof < floor:
                continue
            sym  = (row.get("symbol","") or "").upper()
            score = try_float(row.get("score","0"), 0.0)
            bias  = row.get("bias","")
            why   = row.get("why","")
            ev    = row.get("event_risk","")
            if not sym:
                continue
            cur = best.get(sym)
            if cur is None or asof > cur.asof_utc:
                best[sym] = NewsTilt(asof, sym, score, bias, why, ev)
    return best

def has_been_processed(day: str, run_id: str) -> bool:
    p = STATE / f"tilt_applied-{day}.txt"
    if not p.exists():
        return False
    try:
        with p.open("r") as f:
            return run_id.strip() in {ln.strip() for ln in f}
    except Exception:
        return False

def mark_processed(day: str, run_id: str):
    p = STATE / f"tilt_applied-{day}.txt"
    with p.open("a") as f:
        f.write(run_id.strip() + "\n")

# ------------ combiner ------------
def combine_side(orig_side: str, news_bias: str) -> str:
    o = (orig_side or "").lower()
    n = (news_bias or "").lower()
    if n == "bullish":
        return "Bullish"
    if n == "bearish":
        return "Bearish"
    # neutral or unknown -> keep original if present, else HOLD
    if o in ("bullish","bearish"):
        return orig_side
    return "HOLD"

def combine_score(orig: float, news: float) -> float:
    return float(orig) + float(news)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-min", type=int, default=20, help="only signals newer than N minutes (default: 20)")
    ap.add_argument("--lookback-hours", type=int, default=6, help="news recency window (default: 6h)")
    ap.add_argument("--min-combined", type=float, default=None, help="threshold to notify (default: SCORE_MIN or 35)")
    ap.add_argument("--send", action="store_true", help="send Telegram alerts for qualifying combined signals")
    ap.add_argument("--dry", action="store_true", help="no writes, no state updates, still prints what it would do")
    args = ap.parse_args()

    day = today_tag()
    signals = load_signals(day, since_min=args.since_min)
    newsmap = load_latest_news_tilt(day, lookback_hours=args.lookback_hours)

    if not signals:
        print("No recent signals to combine.")
        return 0

    out_csv = LOGS / f"tilted-{day}.csv"
    new_rows: List[Dict[str,str]] = []

    thr = args.min_combined if args.min_combined is not None else try_float(os.getenv("SCORE_MIN", "35"), 35)

    sent_count = 0
    for s in signals:
        if not s.run_id:
            # skip if we can't de-dup
            continue
        if has_been_processed(day, s.run_id):
            continue

        tilt = newsmap.get(s.symbol)
        news_score = tilt.score if tilt else 0.0
        news_bias  = tilt.bias  if tilt else "Neutral"

        combined = combine_score(s.score, news_score)
        c_side   = combine_side(s.side, news_bias)

        row = {
            "run_id": s.run_id,
            "time_utc": s.time_utc.replace(tzinfo=UTC).isoformat().replace("+00:00","Z"),
            "symbol": s.symbol,
            "tf": s.tf,
            "orig_score": f"{s.score:.1f}",
            "news_score": f"{news_score:.1f}",
            "combined_score": f"{combined:.1f}",
            "orig_side": s.side,
            "news_bias": news_bias,
            "combined_side": c_side,
            "with_news": "1" if tilt else "0",
            "why": (tilt.why if tilt else s.why)[:240],
        }
        new_rows.append(row)

        # alert?
        if args.send and within_session(utcnow()) and combined >= thr:
            msg = (
                f"<b>🧭 Tilted signal</b>\n"
                f"<b>{s.symbol}</b> • {s.tf}\n"
                f"Side: <b>{c_side}</b>\n"
                f"Score: <b>{combined:.1f}</b> (orig {s.score:.1f} {'+' if news_score>=0 else ''}{news_score:.1f})\n"
                f"News: {news_bias}{' • ' + (tilt.why[:120]) if tilt else ''}\n"
                f"at {row['time_utc']}"
            )
            ok, why = (False,None)
            if not args.dry:
                ok, why = send_telegram(msg)
            print(("SENT" if ok else "SEND_FAIL"), s.run_id, why or "")
            if ok:
                sent_count += 1

        # mark processed (state)
        if not args.dry:
            mark_processed(day, s.run_id)

    if not new_rows:
        print("Nothing new to append.")
        return 0

    # append CSV (create header if new)
    if not args.dry:
        create_header = not out_csv.exists()
        with out_csv.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "run_id","time_utc","symbol","tf",
                "orig_score","news_score","combined_score",
                "orig_side","news_bias","combined_side",
                "with_news","why"
            ])
            if create_header:
                w.writeheader()
            w.writerows(new_rows)

    print(f"Combined {len(new_rows)} signal(s); wrote -> {out_csv}")
    if args.send:
        print(f"Telegram alerts sent: {sent_count}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
