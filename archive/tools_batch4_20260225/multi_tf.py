#!/usr/bin/env python3
# tools/multi_tf.py
# Multi-timeframe (H1/H4/D1) snapshot with EMA(20/50) and RSI(14).
# Prints to stdout, or sends to Telegram if --send is used.

import os, sys, json, math, time, datetime as dt
from typing import List, Dict, Optional, Tuple
import urllib.request, urllib.error

# ---------- Config from environment ----------
TD_KEY   = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
AV_KEY   = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# Default timeframes
DEFAULT_TFS = ["1h", "4h", "1day"]  # H1, H4, D1
OUTPUTSIZE  = 300  # candles to fetch before TA (aggregations need buffer)

# ---------- Small HTTP helper ----------
def _get(url: str, timeout: float = 15.0) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bot-a/mtf"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data)
    except Exception:
        return None

# ---------- TA helpers ----------
def ema(series: List[float], n: int) -> List[float]:
    if not series or n <= 1: return series[:]
    k = 2 / (n + 1)
    out = []
    s = series[0]
    out.append(s)
    for x in series[1:]:
        s = x * k + s * (1 - k)
        out.append(s)
    return out

def rsi(series: List[float], n: int = 14) -> List[float]:
    if len(series) < n + 1: return [50.0] * len(series)
    gains, losses = [], []
    for i in range(1, len(series)):
        ch = series[i] - series[i-1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    # first avg
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    rsis = [50.0] * (n)  # align length later
    if avg_loss == 0:
        rs = 999999.0
    else:
        rs = avg_gain / avg_loss
    rsis.append(100 - (100 / (1 + rs)))
    # Wilder smoothing
    for i in range(n, len(gains)):
        avg_gain = (avg_gain*(n-1) + gains[i]) / n
        avg_loss = (avg_loss*(n-1) + losses[i]) / n
        if avg_loss == 0:
            rs = 999999.0
        else:
            rs = avg_gain / avg_loss
        rsis.append(100 - (100 / (1 + rs)))
    # pad to same length as series
    while len(rsis) < len(series):
        rsis.insert(0, 50.0)
    return rsis[:len(series)]

# ---------- Data fetchers ----------
def td_symbol(sym: str) -> str:
    # Expect FX like "EURUSD" or "XAUUSD"
    if len(sym) == 6 and sym.isalpha():
        base, quote = sym[:3], sym[3:]
        return f"{base}/{quote}"
    return sym

def fetch_td(sym: str, interval: str, limit: int) -> Optional[List[Dict]]:
    if not TD_KEY: return None
    s = td_symbol(sym)
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={urllib.parse.quote(s)}"
        f"&interval={interval}"
        f"&outputsize={limit}"
        f"&order=ASC&timezone=UTC&apikey={TD_KEY}"
    )
    js = _get(url)
    if not js or "values" not in js: return None
    vals = js["values"]
    out = []
    for v in vals:
        try:
            out.append({
                "time": v["datetime"],
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
            })
        except Exception:
            continue
    return out if out else None

def fetch_av_fx(sym: str, kind: str, interval: str = "60min", limit: int = 300) -> Optional[List[Dict]]:
    # kind: "INTRADAY" (60min) or "DAILY"
    if not AV_KEY: return None
    base, quote = sym[:3], sym[3:]
    if kind == "DAILY":
        url = ( "https://www.alphavantage.co/query"
                f"?function=FX_DAILY&from_symbol={base}&to_symbol={quote}"
                f"&outputsize=full&apikey={AV_KEY}")
        js = _get(url)
        key = "Time Series FX (Daily)"
    else:
        # Only 60min is supported for FX intraday
        url = ( "https://www.alphavantage.co/query"
                f"?function=FX_INTRADAY&from_symbol={base}&to_symbol={quote}"
                f"&interval={interval}&outputsize=full&apikey={AV_KEY}")
        js = _get(url)
        key = f"Time Series FX ({interval})"
    if not js or key not in js: return None
    # AV returns dict keyed by timestamp; we need ASC order
    items = sorted(js[key].items())
    out = []
    for t, v in items[-limit:]:
        try:
            out.append({
                "time": t,
                "open": float(v["1. open"]),
                "high": float(v["2. high"]),
                "low":  float(v["3. low"]),
                "close":float(v["4. close"]),
            })
        except Exception:
            continue
    return out if out else None

def aggregate_1h_to_4h(rows: List[Dict]) -> List[Dict]:
    if not rows: return []
    out, bucket = [], []
    last_hour = None
    for r in rows:
        t = dt.datetime.fromisoformat(r["time"].replace("Z",""))
        h = t.hour // 4  # 0..5 bucket within day
        key = (t.date(), h)
        if last_hour is None: last_hour = key
        if key != last_hour:
            out.append(_agg_bucket(bucket))
            bucket = []
            last_hour = key
        bucket.append(r)
    if bucket:
        out.append(_agg_bucket(bucket))
    return out

def _agg_bucket(bucket: List[Dict]) -> Dict:
    o = bucket[0]["open"]
    c = bucket[-1]["close"]
    h = max(x["high"] for x in bucket)
    l = min(x["low"]  for x in bucket)
    t = bucket[-1]["time"]
    return {"time": t, "open": o, "high": h, "low": l, "close": c}

# ---------- Load series for a timeframe ----------
def load_ohlc(sym: str, tf: str, limit: int = OUTPUTSIZE) -> Optional[List[Dict]]:
    # Try Twelve Data directly
    td_ok = fetch_td(sym, tf, limit)
    if td_ok: return td_ok
    # Fallback to Alpha Vantage
    if tf == "1h":
        av = fetch_av_fx(sym, "INTRADAY", "60min", limit)
        return av
    if tf == "4h":
        av1h = fetch_av_fx(sym, "INTRADAY", "60min", limit*4)
        return aggregate_1h_to_4h(av1h) if av1h else None
    if tf == "1day":
        avd = fetch_av_fx(sym, "DAILY", limit=limit)
        return avd
    return None

# ---------- Per-TF analysis ----------
def analyze_tf(rows: List[Dict]) -> Optional[Dict]:
    if not rows or len(rows) < 60:  # need enough history
        return None
    closes = [r["close"] for r in rows]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    c = closes[-1]
    e20, e50, rsi_v = ema20[-1], ema50[-1], rsi14[-1]
    if abs(e20 - e50) / max(1e-9, c) < 0.00005:
        trend = "flat"
        trend_emoji = "➖"
    elif e20 > e50:
        trend = "up"
        trend_emoji = "⬆️"
    else:
        trend = "down"
        trend_emoji = "⬇️"
    if rsi_v >= 55:
        bias = "bull"
    elif rsi_v <= 45:
        bias = "bear"
    else:
        bias = "neutral"
    return dict(close=c, ema20=e20, ema50=e50, rsi=rsi_v, trend=trend, trend_emoji=trend_emoji, bias=bias)

def vote(decisions: List[str]) -> str:
    ups = decisions.count("up")
    downs = decisions.count("down")
    if ups >= 2 and ups > downs: return "BUY"
    if downs >= 2 and downs > ups: return "SELL"
    return "HOLD"

# ---------- Compose message ----------
def fmt_price(x: float) -> str:
    # Keep 5 decimals for FX, 2 for gold
    return f"{x:.5f}" if x < 50 else f"{x:.2f}"

def compose(sym: str, tf_results: Dict[str, Dict]) -> str:
    now = dt.datetime.utcnow().strftime("UTC %H:%M")
    lines = []
    lines.append(f"*{sym} – Multi-TF Snapshot*")
    lines.append(f"🕒 {now}")
    tf_order = [("1h","H1"), ("4h","H4"), ("1day","D1")]
    votes = []
    for key, label in tf_order:
        r = tf_results.get(key)
        if not r:
            lines.append(f"{label}: no data")
            continue
        lines.append(
            f"{label}: {r['trend_emoji']}  "
            f"EMA20/50 {fmt_price(r['ema20'])}/{fmt_price(r['ema50'])}  "
            f"RSI14 {r['rsi']:.1f} ({r['bias']})"
        )
        votes.append(r["trend"])
    # summary
    call = vote(votes)
    call_emoji = {"BUY":"🟢","SELL":"🔴","HOLD":"⚪"}.get(call,"⚪")
    lines.append("")
    lines.append(f"*Verdict*: {call_emoji} *{call}* (by majority of TF trends)")
    return "\n".join(lines)

# ---------- Telegram (re-use your safe sender) ----------
def tg_send(text: str, parse_mode: str = "Markdown") -> bool:
    # Minimal inline sender to avoid importing anything else.
    if not (BOT_TOKEN and CHAT_ID):
        print(text)
        print("[mtf] no telegram creds → printed")
        return False
    try:
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8","ignore")
        js = json.loads(body)
        ok = bool(js.get("ok", False))
        if not ok:
            print("[mtf] telegram send failed:", body)
        return ok
    except Exception as e:
        print("[mtf] telegram exception:", e)
        print(text)
        return False

# ---------- CLI ----------
def main(argv: List[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Multi-TF snapshot")
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--tfs", default="1h,4h,1day")
    p.add_argument("--send", action="store_true", help="send to Telegram")
    p.add_argument("--plain", action="store_true", help="send as plain text (no Markdown)")
    args = p.parse_args(argv)

    sym = args.symbol.upper().replace("/", "")
    tfs = [x.strip() for x in args.tfs.split(",") if x.strip()]

    tf_results: Dict[str, Dict] = {}
    for tf in tfs:
        rows = load_ohlc(sym, tf, OUTPUTSIZE)
        if not rows:
            tf_results[tf] = None
            continue
        res = analyze_tf(rows)
        tf_results[tf] = res

    msg = compose(sym, tf_results)

    if args.send:
        pm = "" if args.plain else "Markdown"
        tg_send(msg, parse_mode=pm)
    else:
        print(msg)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
