#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
runner_fetch.py  — single-file fetch + analyze + alert loop
Source: Stooq EURUSD 15m CSV (no API key)
Outputs: eurusd_m15.csv  (timestamp,open,high,low,close,volume)
Alerts: Telegram (env BOT_TOKEN, CHAT_ID)
"""

import os, io, time, ssl, json, math, urllib.request, urllib.parse
from datetime import datetime, timezone
import pandas as pd
import numpy as np

PAIR = "EURUSD"
TIMEFRAME = "M15"
CSV_FILE = "eurusd_m15.csv"

CONF_MIN = float(os.getenv("CONF_MIN", "1.5"))
THROTTLE_SEC = int(os.getenv("THROTTLE_SEC", "300"))

# ---- Telegram (same style as our small helper) ----
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

def send_telegram(text: str) -> bool:
    try:
        if not BOT_TOKEN or not CHAT_ID:
            print("[TG] BOT_TOKEN/CHAT_ID not set; would send:\n", text)
            return False
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            ok = (r.status == 200)
            if not ok:
                print("[TG] HTTP", r.status, r.read())
            return ok
    except Exception as e:
        print("[TG] ERR:", e)
        return False

# ---- Fetch EURUSD M15 from Stooq ----
def fetch_and_save() -> int:
    """Fetch from Stooq, save CSV_FILE; return row count (0 on fail)."""
    try:
        # Example: https://stooq.com/q/d/l/?s=eurusd&i=15
        url = "https://stooq.com/q/d/l/?s=eurusd&i=15"
        # Some Android builds need this to ignore older TLS issues:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        if not raw.strip() or "Date" not in raw:
            print("[FETCH] Stooq returned empty or unexpected CSV")
            return 0

        df = pd.read_csv(io.StringIO(raw))
        # Expected columns: Date, Time, Open, High, Low, Close, Volume
        # Some mirrors use lowercase – normalize:
        cols = {c.lower(): c for c in df.columns}
        need = {"date","time","open","high","low","close"}
        if not need.issubset(set(cols.keys())):
            print("[FETCH] Stooq CSV missing columns; got:", list(df.columns))
            return 0

        date_col = cols["date"]; time_col = cols["time"]
        ocol = cols["open"]; hcol = cols["high"]; lcol = cols["low"]; ccol = cols["close"]
        vcol = cols.get("volume", None)

        ts = pd.to_datetime(df[date_col] + " " + df[time_col], utc=True)
        out = pd.DataFrame({
            "timestamp": ts,
            "open":  df[ocol].astype(float),
            "high":  df[hcol].astype(float),
            "low":   df[lcol].astype(float),
            "close": df[ccol].astype(float),
            "volume": df[vcol].astype(float) if vcol else 0.0,
        }).dropna()
        out = out.sort_values("timestamp").drop_duplicates("timestamp")
        # keep last ~600 rows
        out = out.tail(600)
        out.to_csv(CSV_FILE, index=False)
        print(f"[DONE] Saved {len(out)} candles to {CSV_FILE}")
        return len(out)
    except Exception as e:
        print("[ERROR] fetch_and_save:", e)
        return 0

# ---- Indicator helpers (same logic as light runner) ----
def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def rsi_from_close(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    r = 100 - (100 / (1 + rs))
    val = float(r.iloc[-1]) if not math.isnan(r.iloc[-1]) else 50.0
    return max(0.0, min(100.0, val))

def adx_from_hlc(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    if len(high) < period + 1:
        return 5.0
    up = high.diff(); dn = -low.diff()
    plus_dm = up.where((up > 0) & (up > dn), 0.0)
    minus_dm = dn.where((dn > 0) & (dn > up), 0.0)

    tr1 = (high - low)
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    pdi = 100 * (plus_dm.rolling(period).mean() / atr)
    mdi = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx = dx.rolling(period).mean()
    val = float(adx.iloc[-1]) if not math.isnan(adx.iloc[-1]) else 5.0
    return max(0.0, min(60.0, val))

def macd_hist_from_close(closes: pd.Series, fast=12, slow=26, sig=9) -> float:
    if len(closes) < slow + sig + 1:
        return 0.0
    macd_line = _ema(closes, fast) - _ema(closes, slow)
    signal = _ema(macd_line, sig)
    hist = macd_line - signal
    return float(hist.iloc[-1])

def load_csv() -> pd.DataFrame | None:
    if not os.path.exists(CSV_FILE):
        return None
    try:
        df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
        df = df.sort_values("timestamp")
        return df
    except Exception as e:
        print("[ERROR] load_csv:", e)
        return None

def analyze(df: pd.DataFrame) -> dict:
    closes = df["close"].tail(200)
    highs  = df["high"].tail(200)
    lows   = df["low"].tail(200)

    rsi = rsi_from_close(closes, 14)
    adx = adx_from_hlc(highs, lows, closes, 14)
    mh  = macd_hist_from_close(closes, 12, 26, 9)

    notes = []
    buy_votes = 0
    sell_votes = 0

    if rsi >= 65: 
        buy_votes += 1; notes.append("RSI≥65")
    if rsi <= 35: 
        sell_votes += 1; notes.append("RSI≤35")

    if mh > 0:
        buy_votes += 1; notes.append("ΔMACD>0")
    if mh < 0:
        sell_votes += 1; notes.append("ΔMACD<0")

    strength = 0.6 if adx >= 18 else 0.0
    score = max(buy_votes, sell_votes) * 1.0 + strength

    direction = "FLAT"
    if buy_votes > sell_votes: direction = "BUY"
    if sell_votes > buy_votes: direction = "SELL"
    if direction == "FLAT": notes.append("ADX " + ("≥18" if adx >= 18 else "weak"))
    else:
        if adx >= 18: notes.append("ADX≥18")
        else: notes.append("ADX weak")

    return {
        "rsi": rsi, "adx": adx, "macd_hist": mh,
        "score": score, "direction": direction, "notes": notes
    }

def main():
    print(f"[START] {PAIR} {TIMEFRAME} | Python {'.'.join(map(str, tuple(pd.__version__.split('.')[:1])))}")
    print(f"[INFO] CONF_MIN={CONF_MIN}  THROTTLE_SEC={THROTTLE_SEC}")
    last_ts = None
    last_send_ts = 0

    loop = 0
    while True:
        loop += 1
        print(f"\n[LOOP {loop}] --------------------------")
        rows = fetch_and_save()
        if rows < 50:
            print("[ERROR] Too few rows after fetch; retry in 60s")
            time.sleep(60); continue

        df = load_csv()
        if df is None or len(df) < 50:
            print("[ERROR] CSV load failed; retry in 60s")
            time.sleep(60); continue

        ts = df["timestamp"].iloc[-1]
        new_candle = (last_ts is None) or (ts != last_ts)

        res = analyze(df)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = (f"{stamp} UTC | {PAIR} {TIMEFRAME} | {res['direction']} | "
                f"Score {res['score']:.2f} "
                f"| RSI {res['rsi']:.1f} • ADX {res['adx']:.1f} • ΔMACD {res['macd_hist']:.6f} "
                f"| {' ; '.join(res['notes'])}")
        print(line)

        # Alert conditions
        should_send = (
            res["direction"] != "FLAT" and
            res["score"] >= CONF_MIN and
            new_candle and
            (time.time() - last_send_ts >= THROTTLE_SEC)
        )
        if should_send:
            msg = (f"⚡ <b>{PAIR} {TIMEFRAME} {res['direction']}</b>\n"
                   f"Score {res['score']:.2f}\n"
                   f"RSI {res['rsi']:.1f} | ADX {res['adx']:.1f} | ΔMACD {res['macd_hist']:.6f}\n"
                   f"{' ; '.join(res['notes'])}")
            send_telegram(msg)
            last_send_ts = time.time()

        last_ts = ts
        time.sleep(60)  # poll each minute (15m bars → safe & light)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[STOP] User interrupt")
