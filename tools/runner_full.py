#!/usr/bin/env python3
import os, sys, time, requests, traceback, gc
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# === CONFIG FROM ENV ===
ADX_MIN = float(os.getenv("ADX_MIN", 14))
RSI_BUY = float(os.getenv("RSI_BUY", 62))
RSI_SELL = float(os.getenv("RSI_SELL", 38))
MACD_MIN = float(os.getenv("MACD_MIN", 0.00015))
CONF_MIN = float(os.getenv("CONF_MIN", 0.8))
THROTTLE_SEC = int(os.getenv("THROTTLE_SEC", 60))
LOOP_SEC = int(os.getenv("LOOP_SEC", 60))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CSV_FILE = os.path.join(os.path.dirname(__file__), "eurusd_m15.csv")

# === LOG HELPERS ===
def log_info(msg):
    print(f"[INFO] {datetime.utcnow().isoformat(timespec='seconds')}Z | {msg}", flush=True)

def log_error(msg):
    print(f"[ERROR] {datetime.utcnow().isoformat(timespec='seconds')}Z | {msg}", flush=True)

# === INDICATORS ===
def rsi(series, length=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    roll_up = pd.Series(gain).ewm(alpha=1/length, adjust=False).mean()
    roll_down = pd.Series(loss).ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / roll_down
    rsi_vals = 100.0 - (100.0 / (1.0 + rs))
    return pd.Series(rsi_vals, index=series.index)

def macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line

def adx(high, low, close, length=14):
    high = high.astype(float); low = low.astype(float); close = close.astype(float)
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift()), abs(low - close.shift())))
    atr = pd.Series(tr).ewm(alpha=1/length, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/length, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/length, adjust=False).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/length, adjust=False).mean().fillna(0.0)

# === SIGNAL SCORING ===
def score_row(rsi_val, adx_val, macd_h, direction):
    conf = 0.0
    if adx_val >= ADX_MIN: conf += 0.5
    if abs(macd_h) >= MACD_MIN: conf += 0.3
    if direction != "FLAT": conf += 0.2
    return min(conf, 1.0)

# === TELEGRAM SEND ===
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log_error("Telegram not configured")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 60))
            log_error(f"Telegram rate limit - retry after {retry_after}s")
            time.sleep(retry_after)
            return False
        return r.ok
    except Exception as e:
        log_error(f"Telegram send failed: {e}")
        return False

# === MARKET HOURS ===
def is_trading_hours(utc_dt):
    if utc_dt.weekday() == 5: return False
    if utc_dt.weekday() == 6 and utc_dt.hour < 22: return False
    if utc_dt.weekday() == 4 and utc_dt.hour >= 21: return False
    return True

# === CORE ===
def run_once(last_seen_dt, last_sent_dt):
    if not os.path.exists(CSV_FILE):
        log_error("CSV file not found")
        return last_seen_dt, last_sent_dt

    if not is_trading_hours(datetime.now(timezone.utc)):
        log_info("Market closed - skip loop.")
        return last_seen_dt, last_sent_dt

    df = pd.read_csv(CSV_FILE)
    if len(df) < 50:
        log_error("Insufficient data")
        return last_seen_dt, last_sent_dt

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.dropna()
    close, high, low = df["close"], df["high"], df["low"]

    rsi_val = rsi(close, 14).iloc[-1]
    macd_line, signal_line, macd_hist = macd(close)
    macd_h = macd_hist.iloc[-1]
    adx_val = adx(high, low, close, 14).iloc[-1]

    direction = "FLAT"
    if rsi_val >= RSI_BUY and macd_h > MACD_MIN: direction = "BUY"
    elif rsi_val <= RSI_SELL and macd_h < -MACD_MIN: direction = "SELL"

    conf = score_row(rsi_val, adx_val, macd_h, direction)

    ts = df["timestamp"].iloc[-1]
    if last_seen_dt is not None and ts <= last_seen_dt:
        return last_seen_dt, last_sent_dt
    last_seen_dt = ts

    msg = f"EURUSD M15 {direction} | Score {conf:.2f} | RSI {rsi_val:.1f} | ADX {adx_val:.1f} | ΔMACD {macd_h:.6f}"
    log_info(msg)

    if conf >= CONF_MIN and direction != "FLAT":
        if last_sent_dt is None or ts > last_sent_dt:
            send_telegram(msg)
            last_sent_dt = ts

    return last_seen_dt, last_sent_dt

# === MAIN LOOP ===
def main():
    log_info(f"Runner starting… | Py {sys.version.split()[0]} | ADX_MIN={ADX_MIN}, RSI_BUY={RSI_BUY}, RSI_SELL={RSI_SELL}, MACD_MIN={MACD_MIN}, CONF_MIN={CONF_MIN}, THROTTLE_SEC={THROTTLE_SEC}, LOOP_SEC={LOOP_SEC}")
    last_seen_dt, last_sent_dt = None, None
    consecutive_errors = 0
    while True:
        try:
            last_seen_dt, last_sent_dt = run_once(last_seen_dt, last_sent_dt)
            consecutive_errors = 0
            time.sleep(LOOP_SEC)
        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            backoff = min(60, 5 * (2 ** min(consecutive_errors, 4)))
            log_error(f"Network/API error: {e} | backoff {backoff}s")
            time.sleep(backoff)
        except KeyboardInterrupt:
            log_info("User stop.")
            break
        except Exception as e:
            consecutive_errors += 1
            backoff = min(60, 5 * (2 ** min(consecutive_errors, 4)))
            log_error(f"Loop exception: {e}")
            traceback.print_exc(limit=1)
            time.sleep(backoff)
        finally:
            gc.collect()

if __name__ == "__main__":
    main()
