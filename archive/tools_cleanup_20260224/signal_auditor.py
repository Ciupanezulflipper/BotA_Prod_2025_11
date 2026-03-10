#!/usr/bin/env python3

import os
import sys
import csv
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
import math

import pandas as pd

# --- Config (env overrides) -------------------------------------------------
SIGNALS_CSV = os.getenv("SIGNALS_CSV", os.path.expanduser("~/BotA/logs/signals.csv"))
TRADES_CSV  = os.getenv("TRADES_CSV",  os.path.expanduser("~/BotA/logs/trades.csv"))
SUMMARY_MD  = os.getenv("SUMMARY_MD",  os.path.expanduser("~/BotA/logs/audit_summary.md"))

PAIR        = os.getenv("AUDIT_PAIR", "EURUSD")
TF          = os.getenv("AUDIT_TF", "M15")
LOOKAHEAD_BARS = int(os.getenv("AUDIT_LOOKAHEAD_BARS", "96"))  # 24h on M15
TIMEOUT_EXIT_AT_CLOSE = True  # when timeout, exit at last bar close
USE_PESSIMISTIC_ORDER = True  # if both TP and SL hit same bar, assume SL first

SCORE_COL = os.getenv("SCORE_COL", "score16")  # numeric if available; else "n/a"

# ---------------------------------------------------------------------------

def _parse_timestamp(ts: str) -> datetime:
    # Accept "YYYY-MM-DD HH:MM UTC" or ISO; normalize to aware UTC
    ts = ts.replace(" UTC", "")
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _read_signals(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not os.path.exists(path):
        print(f"✗ signals.csv not found at {path}")
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # Filter by pair/tf (EURUSD/M15 focus)
            if r.get("pair", "").upper() != PAIR.upper():
                continue
            if r.get("tf", "").upper() != TF.upper():
                continue
            rows.append(r)
    return rows

def _to_float(x: str) -> Optional[float]:
    if x is None:
        return None
    x = str(x).strip()
    if x.lower() in ("", "n/a", "na", "none"):
        return None
    try:
        return float(x)
    except Exception:
        return None

def _pip_size(pair: str) -> float:
    return 0.01 if "JPY" in pair.upper() else 0.0001

def _bars_after(provider_rows: List[Dict[str, float]], ts: datetime, max_bars: int) -> pd.DataFrame:
    df = pd.DataFrame(provider_rows)
    # Expect provider rows: time, open, high, low, close
    if "time" not in df or "close" not in df:
        raise RuntimeError("Provider returned invalid OHLC rows")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    # Take bars with time >= signal time (next bar entry is more realistic)
    sub = df[df["time"] >= ts].copy()
    return sub.head(max_bars)

def _first_touch_outcome(direction: str,
                        entry: float, sl: float, tp1: float, tp2: float,
                        bar: pd.Series, pessimistic: bool) -> Optional[Tuple[str, float]]:
    """
    Returns (exit_reason, exit_price) if TP/SL touched within this bar, else None.
    Ordering: if both levels touched, pessimistic decides SL first; otherwise choose
    based on proximity from bar open as a simple heuristic.
    """
    high = float(bar["high"])
    low  = float(bar["low"])
    open_ = float(bar["open"])
    # For SELL: TP below entry, SL above entry
    if direction == "SELL":
        hit_tp1 = low <= tp1
        hit_tp2 = low <= tp2
        hit_sl  = high >= sl
        if (hit_sl and (hit_tp1 or hit_tp2)):
            if pessimistic:
                return ("SL", sl)
            # heuristic: if open closer to TP side, call TP first
            if abs(open_ - tp1) < abs(open_ - sl):
                return ("TP2" if hit_tp2 else "TP1", tp2 if hit_tp2 else tp1)
            return ("SL", sl)
        if hit_tp2:
            return ("TP2", tp2)
        if hit_tp1:
            return ("TP1", tp1)
        if hit_sl:
            return ("SL", sl)
        return None
    else:  # BUY
        hit_tp1 = high >= tp1
        hit_tp2 = high >= tp2
        hit_sl  = low  <= sl
        if (hit_sl and (hit_tp1 or hit_tp2)):
            if pessimistic:
                return ("SL", sl)
            if abs(open_ - tp1) < abs(open_ - sl):
                return ("TP2" if hit_tp2 else "TP1", tp2 if hit_tp2 else tp1)
            return ("SL", sl)
        if hit_tp2:
            return ("TP2", tp2)
        if hit_tp1:
            return ("TP1", tp1)
        if hit_sl:
            return ("SL", sl)
        return None

def _realized_R(direction: str, entry: float, sl: float, tp1: float, exit_px: float) -> float:
    # Define 1R as |entry - SL|
    R = abs(entry - sl)
    if R <= 0:
        return 0.0
    pnl = (exit_px - entry) if direction == "BUY" else (entry - exit_px)
    return pnl / R

def _evaluate_signal(sig: Dict[str, str], provider_rows: List[Dict[str, float]]) -> Dict[str, str]:
    result: Dict[str, str] = dict(sig)  # copy original fields
    direction = sig.get("action", "").upper()
    if direction not in ("BUY", "SELL"):
        result.update({
            "exit_reason": "SKIPPED",
            "exit_ts": "",
            "exit_px": "",
            "realized_R": "",
            "notes": "non-directional action"
        })
        return result

    entry_ts = _parse_timestamp(sig["timestamp_utc"])
    entry = _to_float(sig.get("entry"))
    sl    = _to_float(sig.get("sl"))
    tp1   = _to_float(sig.get("tp1"))
    tp2   = _to_float(sig.get("tp2"))

    if None in (entry, sl, tp1, tp2):
        result.update({
            "exit_reason": "SKIPPED",
            "exit_ts": "",
            "exit_px": "",
            "realized_R": "",
            "notes": "missing risk fields"
        })
        return result

    bars = _bars_after(provider_rows, entry_ts, LOOKAHEAD_BARS)
    if bars.empty:
        result.update({
            "exit_reason": "SKIPPED",
            "exit_ts": "",
            "exit_px": "",
            "realized_R": "",
            "notes": "no forward bars"
        })
        return result

    # Iterate forward until a touch or timeout
    exit_reason = "TIMEOUT"
    exit_px     = float(bars.iloc[-1]["close"]) if TIMEOUT_EXIT_AT_CLOSE else entry
    exit_ts     = bars.iloc[-1]["time"]

    for _, bar in bars.iterrows():
        ot = _first_touch_outcome(direction, entry, sl, tp1, tp2, bar, USE_PESSIMISTIC_ORDER)
        if ot is not None:
            exit_reason, exit_px = ot
            exit_ts = bar["time"]
            break

    realized_R = _realized_R(direction, entry, sl, tp1, exit_px)

    result.update({
        "exit_reason": exit_reason,
        "exit_ts": exit_ts.isoformat(),
        "exit_px": f"{exit_px:.5f}",
        "realized_R": f"{realized_R:.3f}",
        "notes": ""
    })
    return result

def _summarize(trades_df: pd.DataFrame) -> str:
    def _flt(s: pd.Series) -> pd.Series:
        return pd.to_numeric(s, errors="coerce")

    wins1 = (trades_df["exit_reason"] == "TP1").sum()
    wins2 = (trades_df["exit_reason"] == "TP2").sum()
    losses = (trades_df["exit_reason"] == "SL").sum()
    timeouts = (trades_df["exit_reason"] == "TIMEOUT").sum()
    total = len(trades_df)

    realized = _flt(trades_df["realized_R"]).fillna(0.0)
    expectancy = realized.mean() if total else 0.0
    profit_factor = (realized[realized > 0].sum() / abs(realized[realized < 0].sum())) if (realized[realized < 0].sum() != 0) else float("inf")

    # Score calibration (if numeric)
    bucket_lines = []
    if SCORE_COL in trades_df.columns:
        sc = _flt(trades_df[SCORE_COL])
        if sc.notna().any():
            df = trades_df.copy()
            df["__score__"] = sc
            df["__bucket__"] = pd.cut(df["__score__"], bins=[-1,8,12,14,16,999], labels=["0-8","9-12","13-14","15-16",">16"])
            g = df.groupby("__bucket__")["realized_R"].apply(lambda s: pd.to_numeric(s, errors="coerce").mean())
            for k, v in g.items():
                if pd.isna(v): continue
                bucket_lines.append(f"- Score {k}: avg R = {v:.3f}")
    cal_block = "\n".join(bucket_lines) if bucket_lines else "No numeric scores to calibrate."

    md = f"""# BotA Signal Auditor — {PAIR} {TF}

**Sample size:** {total} trades  
- TP1 hits: **{wins1}**
- TP2 hits: **{wins2}**
- SL hits:  **{losses}**
- Timeouts: **{timeouts}**

**Expectancy (avg R/trade):** {expectancy:.3f}  
**Profit factor:** {profit_factor:.2f}

## Score calibration
{cal_block}

## Notes
- Pessimistic bar ordering: {"ON" if USE_PESSIMISTIC_ORDER else "OFF"}
- Timeout horizon: {LOOKAHEAD_BARS} bars
"""
    return md

def main():
    # Load signals
    sigs = _read_signals(SIGNALS_CSV)
    if not sigs:
        print("✗ No signals found to audit.")
        sys.exit(1)

    # Fetch OHLC forward history once (wide window)
    try:
        from BotA.tools.providers import get_ohlc as fetch_ohlc
    except Exception as e:
        print(f"✗ Cannot import providers: {e}")
        sys.exit(1)

    # Pull a generous number of bars to cover all signal times
    bars_needed = max(2000, LOOKAHEAD_BARS + 200)  # safety
    rows, source = [], "unknown"
    try:
        rows = fetch_ohlc(PAIR, TF, bars_needed)
        source = os.getenv("PROVIDER_NAME", "yahoo")
    except Exception as e:
        print(f"✗ OHLC fetch failed: {e}")
        sys.exit(1)
    if not rows:
        print("✗ Provider returned no bars.")
        sys.exit(1)

    results = []
    for sig in sigs:
        try:
            r = _evaluate_signal(sig, rows)
            results.append(r)
        except Exception as e:
            rr = dict(sig)
            rr.update({"exit_reason":"ERROR","exit_ts":"","exit_px":"","realized_R":"","notes":f"{e}"})
            results.append(rr)

    # Write trades.csv
    os.makedirs(os.path.dirname(TRADES_CSV), exist_ok=True)
    all_keys = sorted({k for r in results for k in r.keys()})
    with open(TRADES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_keys)
        w.writeheader()
        for r in results:
            w.writerow(r)

    # Summary
    df = pd.DataFrame(results)
    md = _summarize(df)
    os.makedirs(os.path.dirname(SUMMARY_MD), exist_ok=True)
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write(md)

    print(md.strip())
    print(f"\n✓ wrote {TRADES_CSV}")
    print(f"✓ wrote {SUMMARY_MD}")

if __name__ == "__main__":
    main()
