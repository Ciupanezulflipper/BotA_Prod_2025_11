#!/usr/bin/env python3
# news_signals.py
#
# Create *news-only* trade signals from today's news CSV.
# Writes into logs/tilted-YYYYMMDD.csv using the same schema as tilt_apply.py
# and (optionally) sends Telegram lines for each new trade.
#
# Args:
#   --since-min  N   : scan only news with time_utc >= now- N minutes (default 90)
#   --min-score  S   : require news_score >= S to trade           (default 3)
#   --cooldown   M   : minimum minutes between same-symbol posts  (default 20)
#   --dry             preview only (no file write, no telegram)
#   --send            allow telegram send (default off for safety)
#
# Environment used:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#   WATCHLIST (optional: e.g. "EURUSD,XAUUSD" to limit symbols)
#
# Input CSV (today): logs/news-YYYYMMDD.csv
# Expected columns: run_id,time_utc,asof_utc,symbol,score,bias,why,event_risk,version
#
# Output CSV (append): logs/tilted-YYYYMMDD.csv
# Columns (aligned to tilt_apply.py):
#   run_id,time_utc,asof_utc,symbol,orig_score,news_score,combined_score,
#   orig_side,news_bias,combined_side,with_news,why,version
#
import argparse, csv, hashlib, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import urllib.request

UTC = timezone.utc
ROOT = Path.home() / "bot-a"
LOG_DIR = ROOT / "logs"
TODAY = datetime.now(UTC).strftime("%Y%m%d")

NEWS_CSV = LOG_DIR / f"news-{TODAY}.csv"
OUT_CSV  = LOG_DIR / f"tilted-{TODAY}.csv"
STATE_DIR = ROOT / ".state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / f"news_signals_state-{TODAY}.json"

VERSION = "news_signals_v1"

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state))
    except Exception:
        pass

def tg_send(msg: str) -> str:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat  = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return "missing-telegram-env"
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data, method="POST",
        headers={"Content-Type":"application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            j = json.loads(r.read().decode("utf-8"))
            return "ok" if j.get("ok") else f"tg-error:{j}"
    except Exception as e:
        return f"tg-exc:{e}"

def parse_time(s: str) -> datetime:
    # s like 2025-09-11T06:30:12Z
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(UTC) - timedelta(days=365)

def side_arrow(side: str) -> str:
    return "↑" if side.lower()=="buy" else "↓"

def map_bias_to_trade(symbol: str, bias: str, why: str):
    """
    Convert a USD-centric bias into symbol trade direction.
    Rules (extend as needed):
      * If bias contains 'Bullish' and 'USD'  -> USD strength
      * If bias contains 'Bearish' and 'USD'  -> USD weakness
      * If bias references EUR or GOLD explicitly, respect that
    """
    b = (bias or "").lower()
    w = (why  or "").lower()
    sym = (symbol or "").upper()

    # Direct symbol mentions override generic USD logic
    if "eur" in w or "eurusd" in w:
        if "bullish" in b: return "EURUSD", "buy"
        if "bearish" in b: return "EURUSD", "sell"
    if "gold" in w or "xau" in w or "xauusd" in w:
        if "bullish" in b: return "XAUUSD", "buy"
        if "bearish" in b: return "XAUUSD", "sell"

    # USD-centric mapping
    usd_strong = ("bullish" in b and "usd" in w) or ("usd↑" in w)
    usd_weak   = ("bearish" in b and "usd" in w) or ("usd↓" in w)

    target = sym or "EURUSD"
    if target not in ("EURUSD","XAUUSD"):
        # fall back to WATCHLIST first symbol if present
        wl = [s.strip().upper() for s in (os.getenv("WATCHLIST","EURUSD").split(","))]
        target = wl[0] if wl else "EURUSD"

    if target == "EURUSD":
        if usd_strong: return "EURUSD", "sell"  # USD↑ -> EURUSD↓
        if usd_weak:   return "EURUSD", "buy"   # USD↓ -> EURUSD↑
    if target == "XAUUSD":
        if usd_strong: return "XAUUSD", "sell"  # USD↑ -> Gold↓
        if usd_weak:   return "XAUUSD", "buy"   # USD↓ -> Gold↑

    # If we couldn't deduce, return None
    return None, None

def row_fingerprint(r: dict) -> str:
    base = f"{r.get('time_utc','')}|{r.get('symbol','')}|{r.get('bias','')}|{r.get('why','')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-min", type=int, default=90)
    ap.add_argument("--min-score", type=int, default=3)
    ap.add_argument("--cooldown",  type=int, default=20)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    if not NEWS_CSV.exists():
        print(f"No news file found: {NEWS_CSV}")
        return 0

    # optional WATCHLIST filter
    wl = set([s.strip().upper() for s in os.getenv("WATCHLIST","").split(",") if s.strip()])

    now = datetime.now(UTC)
    since = now - timedelta(minutes=args.since_min)

    # load previous state
    st = load_state()
    last_post = {k: parse_time(v) for k,v in st.get("last_post",{}).items()}
    seen_fp   = set(st.get("seen_fp", []))

    new_rows = []
    alerts = []
    picked = 0

    with NEWS_CSV.open("r", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            t = parse_time(r.get("time_utc",""))
            if t < since: 
                continue

            if wl and r.get("symbol","").upper() not in wl:
                continue

            try:
                score = int(r.get("score","0"))
            except Exception:
                score = 0
            if score < args.min_score:
                continue

            bias = r.get("bias","") or ""
            why  = r.get("why","") or ""
            symbol = (r.get("symbol","") or "").upper()

            tgt, side = map_bias_to_trade(symbol, bias, why)
            if not tgt or not side:
                continue

            # cooldown per symbol
            lp = last_post.get(tgt, datetime.min.replace(tzinfo=UTC))
            if (now - lp) < timedelta(minutes=args.cooldown):
                continue

            fp = row_fingerprint(r)
            if fp in seen_fp:
                continue  # de-dupe identical headline slice

            # Build output row compatible with tilt_apply.py
            news_score = min(10, max(1, score))  # clamp 1..10
            out = {
                "run_id":     r.get("run_id",""),
                "time_utc":   r.get("time_utc",""),
                "asof_utc":   r.get("asof_utc",""),
                "symbol":     tgt,
                "orig_score": 0,
                "news_score": news_score,
                "combined_score": news_score,
                "orig_side":  "-",
                "news_bias":  bias,
                "combined_side": "BUY" if side=="buy" else "SELL",
                "with_news": "True",
                "why": f"{why} • (news-only)",
                "version": VERSION,
            }
            new_rows.append(out)
            seen_fp.add(fp)
            last_post[tgt] = now

            alerts.append(
                f"{tgt} — {out['combined_side']} {side_arrow('buy' if out['combined_side']=='BUY' else 'sell')} "
                f"(news {news_score}/10)\nWhy: {why}"
            )
            picked += 1

    if not new_rows:
        print("No news-only trades to add.")
    else:
        if not args.dry:
            create_header = not OUT_CSV.exists()
            with OUT_CSV.open("a", newline="") as f:
                wr = csv.DictWriter(f, fieldnames=[
                    "run_id","time_utc","asof_utc","symbol",
                    "orig_score","news_score","combined_score",
                    "orig_side","news_bias","combined_side",
                    "with_news","why","version"
                ])
                if create_header:
                    wr.writeheader()
                wr.writerows(new_rows)
            print(f"APPEND: wrote {len(new_rows)} row(s) -> {OUT_CSV}")
        else:
            print(f"DRY: would append {len(new_rows)} rows -> {OUT_CSV}")

        # Telegram
        if args.send and not args.dry:
            msg = "🗞️ News trades\n" + "\n\n".join(alerts)
            res = tg_send(msg)
            print("Telegram:", res)

    # persist state
    st_out = {
        "last_post": {k:v.strftime("%Y-%m-%dT%H:%M:%SZ") for k,v in last_post.items()},
        "seen_fp": list(seen_fp),
        "v": VERSION,
    }
    if not args.dry:
        save_state(st_out)

    return 0

if __name__ == "__main__":
    sys.exit(main())
