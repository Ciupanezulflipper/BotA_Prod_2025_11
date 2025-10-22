#!/usr/bin/env python3
"""
EURUSD M15 signal runner (Termux/Linux)
- Data: TwelveData (15min, 500 bars)
- Indicators: RSI(14), ADX(14), MACD(12,26,9)
- Alerts: Telegram (env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
- Env for data: TWELVEDATA_KEY or TWELVE_DATA_API_KEY
"""

import os
import sys
import time
import math
import traceback
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# -------------------- Config --------------------
PAIR = "EURUSD"
TIMEFRAME = "M15"
CSV_FILE = os.getenv("CSV_FILE", "eurusd_m15.csv")

# gates (can be overridden with env)
CONF_MIN = float(os.getenv("CONF_MIN", "1.5"))       # minimum score to send
THROTTLE_SEC = int(os.getenv("THROTTLE_SEC", "300")) # min seconds between sends
LOOP_SEC = int(os.getenv("LOOP_SEC", "60"))          # loop sleep seconds
ADX_STRONG = float(os.getenv("ADX_STRONG", "18.0"))  # ADX trend threshold

# secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TD_KEY = (os.getenv("TWELVEDATA_KEY", "") or os.getenv("TWELVE_DATA_API_KEY", "")).strip()

# -------------------- Helpers --------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def tele_ok() -> bool:
    return bool(BOT_TOKEN and CHAT_ID)

def send_telegram(text: str) -> bool:
    """Send Telegram message. Returns True on 200 OK. Never raises."""
    try:
        if not tele_ok():
            # silent: user can fix env later; keep loop clean
            return False
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
        r = requests.post(url, data=data, timeout=15)
        return r.status_code == 200
    except Exception:
        return False

def fetch_twelvedata() -> pd.DataFrame | None:
    """Fetch 15m EUR/USD OHLC via TwelveData. Returns DataFrame or None."""
    if not TD_KEY:
        return None
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": "EUR/USD",
            "interval": "15min",
            "outputsize": "500",
            "apikey": TD_KEY,
            "format": "JSON",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        if "values" not in js:
            return None
        df = pd.DataFrame(js["values"])
        # Normalize / order
        # expected keys: datetime, open, high, low, close, volume (volume may be missing)
        if "volume" not in df.columns:
            df["volume"] = 0
        df["timestamp"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
        df = df.sort_values("timestamp")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
        return df
    except Exception:
        return None

def ensure_csv_fresh(max_age_min: int = 30) -> pd.DataFrame | None:
    """Load CSV; if missing/stale fetch from TwelveData and save."""
    need_fetch = True
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            # columns may come as lowercase already
            cols = {c.lower(): c for c in df.columns}
            # normalize names
            df.columns = [c.lower() for c in df.columns]
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
                if df["timestamp"].notna().any():
                    last_ts = df["timestamp"].dropna().iloc[-1]
                    age_min = (utcnow() - last_ts).total_seconds() / 60.0
                    if age_min <= max_age_min and len(df) >= 100:
                        need_fetch = False
                        return df
        except Exception:
            need_fetch = True
    if need_fetch:
        df = fetch_twelvedata()
        if df is None or len(df) < 50:
            return None
        # save normalized, 5 decimals
        df.to_csv(CSV_FILE, index=False, float_format="%.5f")
        return df
    return None

# -------------------- Indicators --------------------
def rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    val = rsi_series.iloc[-1]
    return float(val) if pd.notna(val) else 50.0

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 2:
        return 5.0
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        (high - low),
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
    adx_series = dx.ewm(alpha=1/period, adjust=False).mean()
    val = adx_series.iloc[-1]
    return float(val) if pd.notna(val) else 5.0

def macd(series: pd.Series, fast=12, slow=26, signal=9) -> tuple[float,float,float]:
    if len(series) < slow + signal + 1:
        return (0.0, 0.0, 0.0)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    m = float(line.iloc[-1]); s = float(sig.iloc[-1]); h = float(hist.iloc[-1])
    return (m, s, h)

# -------------------- Strategy / Scoring --------------------
def analyze(df: pd.DataFrame) -> dict:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp","open","high","low","close"])
    df = df.tail(200)  # last 200 for stability

    close = df["close"]
    high = df["high"]
    low = df["low"]

    val_rsi = rsi(close, 14)
    val_adx = adx(high, low, close, 14)
    macd_line, macd_sig, macd_hist = macd(close)

    # direction logic
    direction = "FLAT"
    if macd_hist > 0 and macd_line > macd_sig and val_adx >= ADX_STRONG:
        direction = "BUY"
    elif macd_hist < 0 and macd_line < macd_sig and val_adx >= ADX_STRONG:
        direction = "SELL"

    # score (simple, interpretable)
    score = 0.0
    notes = []

    # ADX contribution
    if val_adx >= ADX_STRONG:
        score += 1.0
        notes.append("💪 ADX strong")
    else:
        notes.append("🧪 ADX weak")

    # MACD momentum
    if macd_hist > 0:
        score += 0.5
        notes.append("📈 ΔMACD>0")
    elif macd_hist < 0:
        score += 0.5
        notes.append("📉 ΔMACD<0")
    else:
        notes.append("ΔMACD≈0")

    # RSI extremes (contrarian nudge)
    if val_rsi <= 35:
        score += 0.3
        notes.append("🔴 RSI≤35")
    elif val_rsi >= 65:
        score += 0.3
        notes.append("🟢 RSI≥65")

    # HTF (coarse): compare last close vs 50EMA to bias
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    if close.iloc[-1] > ema50:
        notes.append("⬆️ HTF↑")
        if direction == "BUY":
            score += 0.2
    else:
        notes.append("⬇️ HTF↓")
        if direction == "SELL":
            score += 0.2

    return {
        "timestamp": df["timestamp"].iloc[-1],
        "price": float(close.iloc[-1]),
        "rsi": float(val_rsi),
        "adx": float(val_adx),
        "macd": float(macd_line),
        "macd_sig": float(macd_sig),
        "macd_hist": float(macd_hist),
        "direction": direction,
        "score": float(score),
        "notes": notes,
    }

def fmt_console(res: dict) -> str:
    ts = res["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"{ts} | {PAIR} {TIMEFRAME} {res['direction']} | "
        f"Score {res['score']:.2f} | RSI {res['rsi']:.1f} • ADX {res['adx']:.1f} "
        f"• ΔMACD {res['macd_hist']:.6f} | {' ; '.join(res['notes'])}"
    )

def fmt_tg(res: dict) -> str:
    ts = res["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
    head = f"⚡ <b>{PAIR} {TIMEFRAME} {res['direction']}</b> | <b>Score {res['score']:.2f}</b>"
    body = (
        f"💰 Price: <code>{res['price']:.5f}</code>\n"
        f"📊 RSI <b>{res['rsi']:.1f}</b> | ADX <b>{res['adx']:.1f}</b> | ΔMACD <b>{res['macd_hist']:.6f}</b>\n"
        f"📝 {', '.join(res['notes'])}\n"
        f"⏰ {ts}"
    )
    return f"{head}\n{body}"

# -------------------- Main Loop --------------------
def main():
    print(f"[START] {PAIR} {TIMEFRAME} | Python {sys.version.split()[0]}")
    print(f"[INFO] CONF_MIN={CONF_MIN:.2f}  THROTTLE_SEC={THROTTLE_SEC}  LOOP_SEC={LOOP_SEC}")

    last_send_ts = 0.0
    last_candle_ts = None
    consecutive_tele_errors = 0

    while True:
        try:
            df = ensure_csv_fresh(max_age_min=30)
            if df is None or len(df) < 50:
                print("[ERROR] No/too few rows; retry in 30s")
                time.sleep(30)
                continue

            res = analyze(df)
            print(fmt_console(res))

            # Decide sending: new candle + throttle + score gate + not FLAT
            curr_ts = res["timestamp"]
            new_candle = (last_candle_ts is None) or (curr_ts != last_candle_ts)
            should_send = (
                (res["direction"] != "FLAT")
                and (res["score"] >= CONF_MIN)
                and new_candle
                and ((time.time() - last_send_ts) >= THROTTLE_SEC)
            )

            if should_send:
                ok = send_telegram(fmt_tg(res))
                if ok:
                    consecutive_tele_errors = 0
                    last_send_ts = time.time()
                else:
                    consecutive_tele_errors += 1
                    # avoid log spam; we still move on
                    if consecutive_tele_errors >= 5:
                        print("[FATAL] Telegram failing repeatedly — check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
                        consecutive_tele_errors = 0

            last_candle_ts = curr_ts
            time.sleep(LOOP_SEC)

        except KeyboardInterrupt:
            print("\n[STOP] User interrupt")
            break
        except Exception as e:
            print("[ERROR]", e)
            traceback.print_exc(limit=1)
            print("Waiting 5s and continuing.")
            time.sleep(5)

if __name__ == "__main__":
    main()
