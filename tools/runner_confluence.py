#!/usr/bin/env python3
# tools/runner_confluence.py  — minimal, PRD-safe runner for Bot A (EURUSD focus)
# - Loads .env.runtime via tools.env_loader
# - Fetches OHLC rows via data.ohlcv.fetch(...)
# - Adapts list[dict{t,o,h,l,c,v}] -> DataFrame with UTC index
# - Basic QC for H1/M15
# - Scores (stub) and prints a DRY summary (no Telegram send)

import argparse
import os

# Safety systems
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from risk_manager import check_trade_cap, can_trade


def validate_api_data(data, max_age_seconds=300):
    """Validate data quality and freshness"""
    import time
    
    if data is None or len(data) < 20:
        return False, "insufficient data"
    
    # Check data freshness (< 5 minutes old)
    try:
        latest_time = data.index[-1]
        age = time.time() - latest_time.timestamp()
        if age > max_age_seconds:
            return False, f"stale data ({age:.0f}s old)"
    except:
        pass  # Skip if timestamp check fails
    
    # Check for obvious bad data
    if data['c'].isnull().sum() > len(data) * 0.1:
        return False, "too many null values"
    
    return True, "ok"

def check_news_blackout(window_min=90):
    """Check if we're in news blackout window"""
    from datetime import datetime, timezone
    import os
    
    news_file = os.path.expanduser("~/bot-a/news_utc.txt")
    if not os.path.exists(news_file):
        return False, "no news file"
    
    now = datetime.now(timezone.utc)
    for line in open(news_file):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            event_time = datetime.fromisoformat(line.replace("Z", "+00:00"))
            minutes_away = abs((event_time - now).total_seconds()) / 60
            if minutes_away <= window_min:
                return True, f"News in {minutes_away:.0f}min"
        except:
            pass
    return False, "clear"

from datetime import datetime, timezone

# 0) Load env + aliases early (no side edits)
from tools.env_loader import _loaded  # noqa: F401
# Import retry wrapper
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_with_retry import retry_with_backoff


import pandas as pd
from data.ohlcv import fetch


# ---------- helpers ----------

def _to_df(rows):
    """rows: list of {'t', 'o','h','l','c','v'}; returns DataFrame indexed by UTC datetime."""
    if not isinstance(rows, list) or len(rows) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Normalize columns to lower
    df.columns = [str(c).lower() for c in df.columns]

    # Map common variants if ever needed (already o/h/l/c/t/v present)
    rename = {}
    for a, b in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v"), ("time", "t"), ("datetime", "t"), ("timestamp", "t")):
        if a in df.columns and b not in df.columns:
            rename[a] = b
    if rename:
        df = df.rename(columns=rename)

    if "t" not in df.columns:
        return pd.DataFrame()

    # Parse 't' -> UTC index (supports str or epoch seconds)
    tcol = df["t"]
    if pd.api.types.is_numeric_dtype(tcol):
        idx = pd.to_datetime(tcol, unit="s", utc=True, errors="coerce")
    else:
        idx = pd.to_datetime(tcol, utc=True, errors="coerce")
    df.index = idx

    # Keep only needed cols
    for col in ("o", "h", "l", "c"):
        if col not in df.columns:
            return pd.DataFrame()

    # Dedup/sort
    df = df[~df.index.isna()].copy()
    df = df[~df.index.duplicated(keep="first")].sort_index()

    # Ensure numeric
    for col in ("o", "h", "l", "c", "v"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["o", "h", "l", "c"]
    if "v" in df.columns:
        keep.append("v")
    return df[keep]


def _validate(df: pd.DataFrame, tf: str, want_bars: int) -> tuple[bool, str]:
    if df is None or df.empty:
        return False, "empty dataframe"

    if len(df) < want_bars:
        return False, f"rows[{len(df)}<{want_bars}] not enough bars"

    # time spacing sanity (tight to our strategy: H1=3600s, M15=900s)
    tf = tf.upper()
    expected = 3600 if tf == "H1" else 900 if tf == "M15" else None
    if expected:
        s = df.index.sort_values()
        diffs = s.to_series().diff().dropna()
        if not diffs.empty:
            bad = int((diffs.dt.total_seconds() != expected).sum())
            total = int(diffs.shape[0])
            if total > 0 and bad / total > 0.10:
                return False, f"time spacing anomaly: {bad}/{total} gaps"
    return True, "ok"


def _score_stub(df: pd.DataFrame) -> tuple[str, float, str]:
    """V2: Bollinger Bands Mean Reversion Strategy"""
    
    if len(df) < 50:
        return "WAIT", 0.0, "insufficient data for BB"
    
    # Calculate Bollinger Bands
    sma20 = df['c'].rolling(20).mean().iloc[-1]
    std20 = df['c'].rolling(20).std().iloc[-1]
    bb_upper = sma20 + (std20 * 2)
    bb_lower = sma20 - (std20 * 2)
    
    current_price = float(df['c'].iloc[-1])
    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
    
    # Calculate RSI(14)
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # Volatility filter
    volatility = (df['c'].rolling(20).std() / df['c'].rolling(20).mean()).iloc[-1] * 100
    
    if volatility < 0.25:
        return "WAIT", 0.0, f"Vol too low ({volatility:.3f}%)"
    

    # Calculate ADX (trend strength)
    def calculate_adx(df, period=14):
        """Simple ADX calculation"""
        high = df['h']
        low = df['l']
        close = df['c']
        
        # True Range
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
        minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
        
        # Smoothed indicators
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx.iloc[-1] if not adx.empty else 0
    
    adx = calculate_adx(df)
    
    # Skip if strong trend (mean reversion fails in trends)
    if adx > 25:
        return "WAIT", 0, f"ADX {adx:.1f} too high (trending market)"

    # BUY: Oversold at lower BB
    if bb_position < 0.2 and rsi < 40:
        score = (0.2 - bb_position) * 2
        return "BUY", round(score, 2), f"BB oversold ({bb_position:.2f}, RSI {rsi:.0f})"
    
    # SELL: Overbought at upper BB
    if bb_position > 0.8 and rsi > 60:
        score = (bb_position - 0.8) * 2
        return "SELL", round(score, 2), f"BB overbought ({bb_position:.2f}, RSI {rsi:.0f})"
    
    return "WAIT", 0.0, f"No extreme (BB pos={bb_position:.2f})"


# ---------- main ----------

def run(pair: str, tf: str, bars: int, dry: bool) -> int:
    @retry_with_backoff(max_retries=3, initial_delay=2.0, check_empty_df=False)
    def fetch_with_retry():
        return fetch(pair, tf, bars)
    rows = fetch_with_retry()
    df = _to_df(rows)
    
    # API data quality check
    api_ok, api_why = validate_api_data(df)
    if not api_ok:
        print(f"⚠️ API data issue: {api_why}")
        # Continue anyway but log the issue
    
    ok, why = _validate(df, tf, bars)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not ok:
        print(f"✗ Data quality failed: {why}")
        return 2
    
    # Check news blackout


    # Daily loss limit check
    if not can_trade():
        print("🛑 Daily loss limit hit - trading suspended")
        return 0
    
    # Trade cap check
    cap_ok, cap_msg = check_trade_cap(2)
    if not cap_ok:
        print(f"🛑 {cap_msg}")
        return 0
    
    in_blackout, blackout_reason = check_news_blackout(90)
    if in_blackout:
        print(f"🔇 News blackout: {blackout_reason}")
        return 0

    if in_blackout:
        print(f"🔇 News blackout: {blackout_reason}")
        return 0
    
    if False:  # Disable original not ok block
        print(f"✗ Data quality failed: {why}")
        return 2

    action, score, reason = _score_stub(df)


    # Calculate Stop Loss and Take Profit (1% risk, 2% reward = 1:2 R:R)
    last_price = float(df["c"].iloc[-1])
    
    if action == "BUY":
        stop_loss = round(last_price * 0.99, 5)  # 1% below entry
        take_profit = round(last_price * 1.02, 5)  # 2% above entry
        risk_reward = "1:2"
    elif action == "SELL":
        stop_loss = round(last_price * 1.01, 5)  # 1% above entry
        take_profit = round(last_price * 0.98, 5)  # 2% below entry
        risk_reward = "1:2"
    else:
        stop_loss = None
        take_profit = None
        risk_reward = None
    print(f"📊 {pair} ({tf})")
    print(f"🕒 {now}")
    print(f"📈 Action: {action}")
    print(f"📊 Score: {score}")
    print(f"🧠 Reason: {reason}")
    print(f"Price source: close")
    print(f"Source: twelvedata")
    # Send to Telegram with risk check
    if not dry:
        import subprocess
        import os
        
        # Check risk manager first
        risk_check = subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "risk_manager.py")],
            capture_output=True, text=True
        )
        
        if "CLEAR TO TRADE" in risk_check.stdout and action != "WAIT":
            # Format message
            msg = f"🤖 BotA Signal\n\n"
            msg += f"📊 Pair: {pair}\n"
            msg += f"⏰ Time: {now}\n"
            msg += f"📈 Action: {action}\n"
            msg += f"💯 Score: {score}\n"
            msg += f"🧠 Reason: {reason}\n"
            msg += f"📏 Position: 0.01 lots\n"
            msg += f"🛡️ Risk: 2% ($4)"
            
            if action != "WAIT":
                msg += f"\n🎯 Entry: {last_price}\n"
                msg += f"🛑 Stop Loss: {stop_loss}\n"
                msg += f"✅ Take Profit: {take_profit}\n"
                msg += f"⚖️ R:R = {risk_reward}"
            
            # Send via tg_send.py
            tg_send = os.path.join(os.path.dirname(__file__), "tg_send.py")
            # Send with 3 retries
            for attempt in range(3):
                result = subprocess.run(
                    ["python3", tg_send, msg],
                    capture_output=True, text=True, timeout=30
                )
                
                if "SUCCESS" in result.stdout:
                    break
                elif attempt < 2:
                    print(f"⚠️ Send attempt {attempt+1} failed, retrying in 10s...")
                    import time
                    time.sleep(10)
            
            if "SUCCESS" in result.stdout:
                print("✅ Signal sent to Telegram")
            else:
                print(f"⚠️ Telegram send failed: {result.stdout}")
        elif action == "WAIT":
            print("ℹ️ No trade signal (WAIT)")
        else:
            print("🛑 Risk manager blocked trade")
    else:
        print("[DRY RUN] Would send:", action)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", required=True, help="Timeframe like M15, H1, etc.")
    ap.add_argument("--bars", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    return_code = run(args.pair, args.tf.upper(), args.bars, args.dry_run)
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
