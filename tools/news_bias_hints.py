#!/usr/bin/env python3
import os, csv, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ---- config (env with sane defaults) ----
LOG_DIR   = Path.home()/ "bot-a" / "logs"
WINDOW_MIN = int(os.getenv("NEWS_HINT_WINDOW_MIN", "120"))     # lookback for hints
MIN_SCORE  = int(os.getenv("NEWS_HINT_MIN_SCORE",  "3"))       # low bar for a hint
SYMS       = [s.strip().upper() for s in (os.getenv("WATCHLIST","EURUSD,XAUUSD")).split(",") if s.strip()]

CHAT_ID    = (os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID".upper()) or "").strip()
BOT_TOKEN  = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()

def send_telegram(text: str) -> bool:
    if not CHAT_ID or not BOT_TOKEN: return False
    import json, urllib.request
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": int(CHAT_ID), "text": text}
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:
        return False

def load_news_rows(day:str):
    f = LOG_DIR / f"news-{day}.csv"
    if not f.exists(): return []
    rows = []
    with f.open() as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            rows.append(r)
    return rows

def parse_dt(s:str):
    try:
        # time_utc is like 2025-09-11T06:30:12Z
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        return None

def bias_sign(bias:str) -> int:
    if not bias: return 0
    b = bias.lower()
    if "bull" in b: return +1
    if "bear" in b: return -1
    return 0

def main():
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    rows = load_news_rows(day)
    if not rows:
        print("No news file for today; nothing to hint.")
        return 0

    cutoff = now - timedelta(minutes=WINDOW_MIN)
    best = {s: {"score":0, "bias":0, "why":None, "t":None} for s in SYMS}

    for r in rows:
        sym  = r.get("symbol","").upper()
        if sym not in best: continue
        try: score = int(r.get("score","0"))
        except: score = 0
        if score < MIN_SCORE: continue
        t = parse_dt(r.get("time_utc","")) or parse_dt(r.get("asof_utc",""))
        if not t or t < cutoff: continue
        b  = bias_sign(r.get("bias",""))
        why = r.get("why","").strip()
        # keep the row with the strongest |score|
        if abs(score) > abs(best[sym]["score"]):
            best[sym] = {"score":score, "bias":b, "why":why, "t":t}

    picks = []
    for s in SYMS:
        info = best[s]
        if info["score"] >= MIN_SCORE and info["bias"] != 0:
            arrow = "↑" if info["bias"]>0 else "↓"
            dirn  = "BUY" if info["bias"]>0 else "SELL"
            picks.append((s, dirn, arrow, info["score"], info["why"]))

    if not picks:
        print("No bias hints in window.")
        return 0

    # Build message
    hhmm = now.strftime("%H:%M")
    lines = [f"📰 News bias hints (UTC {hhmm})"]
    for s,dirn,arrow,score,why in picks:
        lines.append(f"• {s}: {dirn} {arrow}  (news {score}/10)")
        if why:
            # keep it short
            short = (why[:160] + "…") if len(why)>160 else why
            lines.append(f"  Why: {short}")

    msg = "\n".join(lines)

    # write CSV
    out = LOG_DIR / f"bias-{day}.csv"
    newfile = not out.exists()
    with out.open("a", newline="") as fh:
        wr = csv.writer(fh)
        if newfile:
            wr.writerow(["time_utc","symbol","dir","score","why"])
        for s,dirn,arrow,score,why in picks:
            wr.writerow([now.isoformat(), s, dirn, score, why])

    ok = send_telegram(msg)
    print(("Telegram sent." if ok else "Telegram skipped."), f"Wrote -> {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
