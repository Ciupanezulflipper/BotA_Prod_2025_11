#!/usr/bin/env python3
"""
Minimal PRD-safe runner that:
- fetches candles via provider_mux (Yahoo→Finnhub fallback),
- computes EMA9/EMA21 + RSI14,
- emits BUY/SELL/WAIT,
- increments daily cap only on BUY/SELL,
- sends Telegram only for BUY/SELL (noise suppressed).

Usage:
  python3 tools/runner_confluence_mux.py --pair EURUSD --tf 15
ENV:
  SUPPRESS_NOISE_ERRORS=1   # do not Telegram provider errors (default 1)
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID  # for sending real signals
"""

from __future__ import annotations
import os, math, json, argparse, subprocess, sys
from typing import List, Dict, Tuple

from tools.provider_mux import fetch_candles

SUPPRESS_NOISE = os.getenv("SUPPRESS_NOISE_ERRORS", "1") != "0"

# ---------- Indicators ----------
def ema(values: List[float], period: int) -> List[float]:
    if not values or period <= 1:
        return values[:]
    k = 2.0 / (period + 1)
    out = []
    s = sum(values[:period]) / period
    out.extend([float("nan")] * (period - 1))
    out.append(s)
    for v in values[period:]:
        s = v * k + s * (1 - k)
        out.append(s)
    return out

def rsi(values: List[float], period: int = 14) -> List[float]:
    if len(values) < period + 1:
        return [float("nan")] * len(values)
    gains, losses = [], []
    for i in range(1, period + 1):
        ch = values[i] - values[i-1]
        gains.append(max(ch, 0.0))
        losses.append(abs(min(ch, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out = [float("nan")] * period
    rs = (avg_gain / avg_loss) if avg_loss != 0 else 1000.0
    out.append(100 - (100 / (1 + rs)))
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i-1]
        gain = max(ch, 0.0)
        loss = abs(min(ch, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = (avg_gain / avg_loss) if avg_loss != 0 else 1000.0
        out.append(100 - (100 / (1 + rs)))
    return out

# ---------- Telegram ----------
def send_signal(text: str) -> Tuple[bool, str]:
    try:
        from tools.telegramalert import send_telegram_message
        ok, err = send_telegram_message(text)
        return bool(ok), err or ""
    except Exception as e:
        return False, str(e)

# ---------- Risk cap ----------
def risk_increment() -> None:
    try:
        subprocess.run(
            ["python3", os.path.expanduser("~/BotA/tools/risk_manager.py"), "increment"],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
    except Exception:
        pass

# ---------- Decision ----------
def decide(pair: str, tf: int) -> Tuple[str, str]:
    provider, rows = fetch_candles(pair, tf, 220)
    if len(rows) < 60:
        raise RuntimeError(f"Insufficient data: {len(rows)} bars")

    closes = [r["c"] for r in rows]
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    r = rsi(closes, 14)

    c = closes[-1]
    e9v, e21v, rsiv = e9[-1], e21[-1], r[-1]

    decision = "WAIT"
    if e9v > e21v and rsiv >= 52:
        decision = "BUY"
    elif e9v < e21v and rsiv <= 48:
        decision = "SELL"

    # very rough SL/TP for demonstration (ATR-lite via std of last 14 diffs)
    diffs = [abs(closes[i]-closes[i-1]) for i in range(len(closes)-14, len(closes))]
    atr = (sum(diffs)/len(diffs)) if diffs else c * 0.0015
    if decision == "BUY":
        sl = c - 2.0*atr
        tp = c + 2.0*atr
    elif decision == "SELL":
        sl = c + 2.0*atr
        tp = c - 2.0*atr
    else:
        sl = tp = 0.0

    msg = f"📈 {decision} {pair} M{tf}\\nEntry {c:.5f} • SL {sl:.5f} • TP {tp:.5f} (prov: {provider})"
    return decision, msg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", type=int, required=True)
    args = ap.parse_args()

    try:
        decision, message = decide(args.pair.upper().replace("/", ""), int(args.tf))
    except Exception as e:
        if not SUPPRESS_NOISE:
            send_signal(f"🚨 BotA Alert\n{e}")
        # exit non-zero for launcher to log; but keep quiet in Telegram
        print(f"ERROR: {e}")
        raise SystemExit(2)

    if decision in ("BUY", "SELL"):
        ok, err = send_signal(message)
        risk_increment()
        print(("OK" if ok else f"SEND_FAIL: {err}"), message)
    else:
        print("WAIT", message)

if __name__ == "__main__":
    main()
