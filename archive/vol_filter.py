#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import re
import json
from typing import Dict, List

# -------------------------------------------------------------------
# Bot A — Volatility filter v2.2
#
# Purpose:
#   - Read recent H1 closes from run.log snapshots.
#   - Compute standard deviation of PERCENT RETURNS over last N steps.
#   - Apply per-symbol volatility thresholds, with sensible defaults.
#   - Drop alerts where vol_ok == False (strict capital-protection mode).
#
# Design (aligned with Rulebook v2.2 and audits):
#   - STD = std of percent returns:
#       r[i] = (close[i] - close[i-1]) / close[i-1]
#   - Needs at least N+1 closes to get N returns.
#   - Base threshold VOL_MIN_STD is interpreted as a PERCENT move,
#     e.g. 0.00015 ≈ 0.015%.
#   - Optional per-symbol overrides via:
#       VOL_MIN_STD_EURUSD
#       VOL_MIN_STD_GBPUSD
#       VOL_MIN_STD_XAUUSD
#       (symbol name uppercased, non-alphanumerics stripped)
#
# Inputs:
#   - JSON array from stdin, each item must contain at least:
#       { "pair": "EURUSD", ... }
#
# Outputs:
#   - JSON array with items enriched by:
#       "vol_std":  <float>   # std of percent returns
#       "vol_ok":   <bool>
#   - Only items with vol_ok == True are kept (strict filter).
# -------------------------------------------------------------------

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
H1_RE = re.compile(
    r"^H1:\s+t=[^ ]+\s+close=([0-9.]+)\s+EMA9=[0-9.]+\s+EMA21=[0-9.]+\s+RSI14=(?:[0-9.]+|NA)\s+MACD_hist=(?:[-\d.]+|NA)\s+vote=[+\-]?\d+"
)


def load_h1_closes() -> Dict[str, List[float]]:
    """
    Parse run.log and collect H1 closes per symbol.

    Expected pattern in run.log:

        === EUR/USD snapshot ===
        H1: t=... close=1.10000 EMA9=... EMA21=... RSI14=... MACD_hist=... vote=...

    Symbols are normalized (slashes removed, uppercased), e.g. "EURUSD".
    """
    closes: Dict[str, List[float]] = {}
    try:
        with open(RUN_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return closes

    cur: str | None = None
    for ln in lines:
        h = HEADER_RE.match(ln.strip())
        if h:
            cur = h.group(1).replace("/", "").upper()
            continue
        if cur:
            m = H1_RE.match(ln.strip())
            if m:
                try:
                    val = float(m.group(1))
                except ValueError:
                    continue
                closes.setdefault(cur, []).append(val)
    return closes


def last_n_std_pct(x: List[float], n: int) -> float:
    """
    Standard deviation of percent returns over last n steps.

    percent_return[i] = (close[i] - close[i-1]) / close[i-1]

    Requires at least n+1 closes to compute n returns.
    If not enough data or invalid values, returns 0.0.
    """
    if len(x) < n + 1:
        return 0.0

    rets: List[float] = []
    prev = x[0]
    for v in x[1:]:
        if prev <= 0:
            prev = v
            continue
        rets.append((v - prev) / prev)
        prev = v

    if len(rets) < n:
        return 0.0

    window = rets[-n:]
    m = sum(window) / len(window)
    var = sum((v - m) ** 2 for v in window) / len(window)
    return var ** 0.5


def symbol_key(sym: str) -> str:
    """
    Normalize symbol name for env overrides, e.g.:

        "EUR/USD"  -> "EURUSD"
        "xauusd"   -> "XAUUSD"
    """
    return re.sub(r"[^A-Z0-9]", "", sym.upper())


def main() -> int:
    # Window length in returns (default 20 H1 steps)
    try:
        n = int(os.getenv("VOL_MIN_COUNT", "20"))
    except ValueError:
        n = 20

    # Base threshold in percent units (e.g. 0.00015 ≈ 0.015%)
    try:
        base_thresh = float(os.getenv("VOL_MIN_STD", "0.00015"))
    except ValueError:
        base_thresh = 0.00015

    raw = sys.stdin.read().strip()
    try:
        arr = json.loads(raw) if raw else []
    except Exception:
        arr = []

    h1 = load_h1_closes()
    out = []

    for it in arr:
        pair = it.get("pair", "").upper()
        closes = h1.get(pair, [])
        std_pct = last_n_std_pct(closes, n)

        it2 = dict(it)
        it2["vol_std"] = std_pct

        skey = symbol_key(pair) if pair else ""
        env_key = f"VOL_MIN_STD_{skey}" if skey else ""

        thresh = base_thresh
        if env_key:
            # Per-symbol override, e.g. VOL_MIN_STD_EURUSD, VOL_MIN_STD_GBPUSD, VOL_MIN_STD_XAUUSD
            env_val = os.getenv(env_key, "")
            if env_val:
                try:
                    thresh = float(env_val)
                except ValueError:
                    thresh = base_thresh

        it2["vol_ok"] = std_pct >= thresh

        # Strict mode: only keep alerts when volatility is acceptable
        if it2["vol_ok"]:
            out.append(it2)

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
