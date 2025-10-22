#!/usr/bin/env python3
"""
final_runner.py - EURUSD multi-timeframe signal generator with optional Telegram alerts.

Usage:
    python -m BotA.tools.final_runner --symbol EURUSD [--dry|--send]

Env flags (all optional):
    RELAX_VOTE=1           -> BUY if sum>=1, SELL if sum<=-1 (default needs 2/-2)
    USE_ADX=1              -> require ADX>=ADX_THR on H4 or D1
    ADX_THR=18             -> ADX threshold (default 18)
    DISABLE_INSIDE_DAY=1   -> disables inside-day suppressor (enabled by default)
    USE_BREAKOUT=1         -> require H1 20-bar breakout in the signal direction
    QUIET_NEWS=1           -> neutralize if news within NEWS_WINDOW_MIN of now
    NEWS_WINDOW_MIN=60     -> minutes window for QUIET_NEWS (default 60)
    ENHANCED_MSG=1         -> richer Telegram text
    PROVIDER_ORDER=...     -> comma-separated preference for providers
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import pandas as pd

# -------------------- Providers --------------------
try:
    from BotA.tools.providers import get_ohlc
except Exception as e:
    print(f"ERROR: Cannot import BotA.tools.providers.get_ohlc -> {e}")
    sys.exit(1)

# -------------------- Telegram fallbacks --------------------
def _dummy_send(msg: str) -> bool:
    print("WARNING: Telegram module not available, message not sent.")
    return False

send_telegram_message = _dummy_send
try:
    from BotA.tools.telegramalert import send_telegram_message as send_telegram_message  # type: ignore
except Exception:
    try:
        from BotA.tools.telegramsender import send_telegram_message as send_telegram_message  # type: ignore
    except Exception:
        try:
            from BotA.tools.telegram_smoke import send_telegram_message as send_telegram_message  # type: ignore
        except Exception:
            pass  # keep dummy


# ============================================================================
# Indicators
# ============================================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    s = pd.Series(series, dtype=float)
    delta = s.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.ewm(span=period, adjust=False).mean()
    roll_down = down.ewm(span=period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, 1e-10)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.ffill().fillna(50.0)
    return out

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    s = pd.Series(series, dtype=float)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    h = pd.Series(high, dtype=float)
    l = pd.Series(low, dtype=float)
    c = pd.Series(close, dtype=float)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr = tr.bfill(limit=1)
    return tr.ewm(span=period, adjust=False).mean()

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    h = pd.Series(high, dtype=float)
    l = pd.Series(low, dtype=float)
    c = pd.Series(close, dtype=float)

    up_move = h.diff()
    down_move = (-l.diff())

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=h.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=h.index)

    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr = tr.bfill(limit=1)
    atr_val = tr.ewm(span=period, adjust=False).mean()

    plus_di = 100.0 * plus_dm.ewm(span=period, adjust=False).mean() / atr_val.replace(0.0, 1e-10)
    minus_di = 100.0 * minus_dm.ewm(span=period, adjust=False).mean() / atr_val.replace(0.0, 1e-10)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, 1e-10)
    return dx.ewm(span=period, adjust=False).mean()


# ============================================================================
# Data fetch & feature compute
# ============================================================================

def _ensure_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def fetch_and_compute(symbol: str, tf: str, min_bars: int = 30) -> Dict[str, Any]:
    try:
        rows, source = get_ohlc(symbol, tf, bars=200)
        if not rows or len(rows) < min_bars:
            return {"error": f"Insufficient data: {0 if not rows else len(rows)} bars"}

        df = pd.DataFrame(rows)
        if df.empty:
            return {"error": "Empty dataframe"}

        df = _ensure_numeric(df, ["open", "high", "low", "close"])
        df = df.dropna(subset=["close"])
        if len(df) < min_bars:
            return {"error": f"Insufficient clean data: {len(df)} bars"}

        df["ema9"] = ema(df["close"], 9)
        df["ema21"] = ema(df["close"], 21)
        df["rsi14"] = rsi(df["close"], 14)
        _, _, df["macd_hist"] = macd(df["close"])
        df["atr14"] = atr(df["high"], df["low"], df["close"], 14)
        df["adx14"] = adx(df["high"], df["low"], df["close"], 14)

        last = df.iloc[-1]
        out = {
            "time": last.get("time", ""),
            "open": float(last["open"]) if pd.notna(last.get("open")) else None,
            "high": float(last["high"]) if pd.notna(last.get("high")) else None,
            "low": float(last["low"]) if pd.notna(last.get("low")) else None,
            "close": float(last["close"]) if pd.notna(last.get("close")) else None,
            "ema9": float(last["ema9"]) if pd.notna(last.get("ema9")) else None,
            "ema21": float(last["ema21"]) if pd.notna(last.get("ema21")) else None,
            "rsi14": float(last["rsi14"]) if pd.notna(last.get("rsi14")) else None,
            "macd_hist": float(last["macd_hist"]) if pd.notna(last.get("macd_hist")) else None,
            "atr14": float(last["atr14"]) if pd.notna(last.get("atr14")) else None,
            "adx14": float(last["adx14"]) if pd.notna(last.get("adx14")) else None,
            "source": source,
            "df": df,
            "error": None
        }
        return out
    except Exception as e:
        return {"error": str(e)}

def compute_vote(d: Dict[str, Any]) -> int:
    if d.get("error"):
        return 0
    ema9, ema21 = d.get("ema9"), d.get("ema21")
    r, m = d.get("rsi14"), d.get("macd_hist")
    if None in (ema9, ema21, r, m):
        return 0
    bull = (ema9 > ema21) and (r > 50) and (m > 0)
    bear = (ema9 < ema21) and (r < 50) and (m < 0)
    return 1 if bull else (-1 if bear else 0)


# ============================================================================
# Filters (light & safe)
# ============================================================================

def check_inside_day(d1: Dict[str, Any]) -> bool:
    if d1.get("error") or "df" not in d1:
        return False
    df = d1["df"]
    if len(df) < 2:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    last_range = float(last["high"] - last["low"])
    prev_range = float(prev["high"] - prev["low"])
    if last_range >= prev_range:
        return False
    mid = float((last["high"] + last["low"]) / 2.0)
    close = float(last["close"])
    return abs(close - mid) < (last_range * 0.3)

def check_breakout(h1: Dict[str, Any], direction: str) -> bool:
    if h1.get("error") or "df" not in h1:
        return False
    df = h1["df"]
    if len(df) < 21:
        return False
    last_close = float(df.iloc[-1]["close"])
    window = df.iloc[-21:-1]
    if direction == "BUY":
        return last_close >= float(window["high"].max())
    if direction == "SELL":
        return last_close <= float(window["low"].min())
    return False

def check_adx_filter(h4: Dict[str, Any], d1: Dict[str, Any], thr: float) -> bool:
    a4 = None if h4.get("error") else h4.get("adx14")
    a1 = None if d1.get("error") else d1.get("adx14")
    if a4 is not None and a4 >= thr:
        return True
    if a1 is not None and a1 >= thr:
        return True
    return False

def check_news_window(news_file: str, window_minutes: int) -> bool:
    if not os.path.isfile(news_file):
        return False
    now = datetime.now(timezone.utc)
    try:
        with open(news_file, "r") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                try:
                    ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
                except Exception:
                    continue
                delta_min = abs((ts - now).total_seconds()) / 60.0
                if delta_min <= float(window_minutes):
                    return True
    except Exception:
        return False
    return False


# ============================================================================
# Decision & Levels
# ============================================================================

def decide_signal(
    votes: Dict[str, int],
    h1: Dict[str, Any],
    h4: Dict[str, Any],
    d1: Dict[str, Any],
    env: Dict[str, Any]
) -> Tuple[str, str]:
    vote_sum = int(sum(votes.values()))
    relax = bool(env.get("RELAX_VOTE", False))
    buy_thr = 1 if relax else 2
    sell_thr = -1 if relax else -2

    if vote_sum >= buy_thr:
        decision = "BUY"
    elif vote_sum <= sell_thr:
        decision = "SELL"
    else:
        return ("NEUTRAL", f"Vote sum {vote_sum} below threshold")

    if not env.get("DISABLE_INSIDE_DAY", False):
        if check_inside_day(d1):
            return ("NEUTRAL", "Inside-day on D1 -> suppress")

    if env.get("USE_ADX", False):
        thr = float(env.get("ADX_THR", 18))
        if not check_adx_filter(h4, d1, thr):
            return ("NEUTRAL", f"ADX below {thr} on H4 & D1")

    if env.get("USE_BREAKOUT", False):
        if not check_breakout(h1, decision):
            return ("NEUTRAL", f"Breakout not confirmed on H1 for {decision}")

    if env.get("QUIET_NEWS", False):
        news_file = os.path.expanduser("~/BotA/events_utc.txt")
        minutes = int(env.get("NEWS_WINDOW_MIN", 60))
        if check_news_window(news_file, minutes):
            return ("NEUTRAL", f"News within {minutes} min")

    return (decision, f"All filters passed, vote sum={vote_sum}")

def compute_levels(
    decision: str,
    h1: Dict[str, Any],
    h4: Dict[str, Any],
    d1: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    ref = None
    for d in (d1, h4, h1):
        if not d.get("error") and d.get("close") is not None:
            ref = d
            break
    if ref is None:
        return (None, None, None, None)

    entry = float(ref.get("close"))
    atr_val = ref.get("atr14")
    if atr_val is None or not np.isfinite(atr_val) or atr_val <= 0:
        return (None, None, None, None)

    max_atr = entry * 0.05
    atr_val = float(min(atr_val, max_atr))

    sl_dist = 1.5 * atr_val
    tp_dist = 2.0 * atr_val

    if decision == "BUY":
        sl = entry - sl_dist
        tp = entry + tp_dist
    elif decision == "SELL":
        sl = entry + sl_dist
        tp = entry - tp_dist
    else:
        return (None, None, None, None)

    return (round(entry, 5), round(sl, 5), round(tp, 5), round(atr_val, 5))


# ============================================================================
# Messaging
# ============================================================================

def format_telegram_message(
    symbol: str,
    decision: str,
    entry: float,
    sl: float,
    tp: float,
    votes: Dict[str, int],
    source: str,
    enhanced: bool = False
) -> str:
    emoji = "🟢" if decision == "BUY" else "🔴"
    now_txt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rr = abs(tp - entry) / max(abs(sl - entry), 1e-10)
    lines = [
        f"{emoji} {symbol} | {decision}",
        f"⏰ {now_txt}",
        f"📈 Entry: {entry:.5f}",
        f"🎯 TP: {tp:.5f} | 🛑 SL: {sl:.5f}",
        f"⚖️ RR: 1:{rr:.2f}",
        f"🗳️ Votes: {votes} | 📡 {source}"
    ]
    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="EURUSD signal generator")
    parser.add_argument("--symbol", default="EURUSD", help="Trading symbol")
    parser.add_argument("--dry", action="store_true", help="Dry run (no Telegram)")
    parser.add_argument("--send", action="store_true", help="Send Telegram if actionable")
    args = parser.parse_args()

    symbol = (args.symbol or "EURUSD").upper()

    env = {
        "RELAX_VOTE": os.getenv("RELAX_VOTE", "0") == "1",
        "USE_ADX": os.getenv("USE_ADX", "0") == "1",
        "ADX_THR": float(os.getenv("ADX_THR", "18")),
        "DISABLE_INSIDE_DAY": os.getenv("DISABLE_INSIDE_DAY", "0") == "1",
        "USE_BREAKOUT": os.getenv("USE_BREAKOUT", "0") == "1",
        "QUIET_NEWS": os.getenv("QUIET_NEWS", "0") == "1",
        "NEWS_WINDOW_MIN": int(os.getenv("NEWS_WINDOW_MIN", "60")),
        "ENHANCED_MSG": os.getenv("ENHANCED_MSG", "0") == "1",
    }

    tfs = ["H1", "H4", "D1"]
    data: Dict[str, Dict[str, Any]] = {tf: fetch_and_compute(symbol, tf) for tf in tfs}

    print(f"=== {symbol} snapshot ===")
    for tf in tfs:
        d = data[tf]
        if d.get("error"):
            print(f"{tf}: ERROR -> {d['error']}")
        else:
            ts = d.get("time", "N/A")
            close = d.get("close"); ema9_v = d.get("ema9"); ema21_v = d.get("ema21")
            r = d.get("rsi14"); mh = d.get("macd_hist"); src = d.get("source", "N/A")
            vote = compute_vote(d)
            cs = "N/A" if close is None else f"{close:.5f}"
            e9 = "N/A" if ema9_v is None else f"{ema9_v:.5f}"
            e21 = "N/A" if ema21_v is None else f"{ema21_v:.5f}"
            rs = "N/A" if r is None else f"{r:.2f}"
            ms = "N/A" if mh is None else f"{mh:.5f}"
            print(f"{tf}: t={ts} close={cs} EMA9={e9} EMA21={e21} RSI14={rs} MACD_hist={ms} vote={vote:+d} src={src}")
    print()

    votes = {tf: compute_vote(data[tf]) for tf in tfs}
    decision, reason = decide_signal(votes, data["H1"], data["H4"], data["D1"], env)

    if decision == "NEUTRAL":
        print(f"No actionable signal. ({reason})")
        return

    entry, sl, tp, atr_val = compute_levels(decision, data["H1"], data["H4"], data["D1"])
    if None in (entry, sl, tp, atr_val):
        print("No actionable signal. (Unable to compute SL/TP)")
        return

    source = "unknown"
    for tf in ["D1", "H4", "H1"]:
        if not data[tf].get("error"):
            source = data[tf].get("source", "unknown")
            break

    print(f"Signal: {decision}")
    print(f"Entry: {entry:.5f}")
    print(f"SL: {sl:.5f}")
    print(f"TP: {tp:.5f}")
    print(f"ATR: {atr_val:.5f}")
    print(f"Votes: {votes}")
    print(f"Reason: {reason}")
    print()

    if args.send:
        msg = format_telegram_message(symbol, decision, entry, sl, tp, votes, source, env.get("ENHANCED_MSG", False))
        try:
            ok = bool(send_telegram_message(msg))
            if ok:
                print("Telegram sent.")
            else:
                print("Telegram send failed.")
        except Exception as e:
            print(f"Telegram error: {e}")
    else:
        print("Dry run mode - no Telegram message sent.")

if __name__ == "__main__":
    main()
