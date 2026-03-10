#!/usr/bin/env python3
"""
auditor.py — Backtest BotA signals. Stdlib-only rewrite (no pandas).
Public API: fetch_future_bars(), simulate_trade(), pip_size_for()
"""
import os, sys, csv
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

def pip_size_for(pair: str) -> float:
    return 0.01 if str(pair).upper().endswith("JPY") else 0.0001

def _parse_ts(s: str) -> Optional[datetime]:
    if not s: return None
    try:
        s = str(s).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _sf(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if f != f else f  # nan check
    except Exception:
        return d

def fetch_future_bars(pair: str, tf: str, after_time: datetime, bars: int) -> Optional[List[Dict]]:
    try:
        from BotA.tools.providers import get_ohlc
    except ImportError:
        return None
    try:
        rows, source = get_ohlc(pair, tf, bars * 4)
    except Exception:
        return None
    if not rows:
        return None

    result = []
    for r in rows:
        t = _parse_ts(str(r.get("time", "")))
        if t is None: continue
        o = _sf(r.get("open"));  h = _sf(r.get("high"))
        l = _sf(r.get("low"));   c = _sf(r.get("close"))
        if not c: continue
        if t > after_time:
            result.append({"time": t, "open": o, "high": h, "low": l, "close": c})

    result.sort(key=lambda x: x["time"])
    return result[:bars] if result else None

def simulate_trade(action, entry, sl, tp1, tp2, tp3,
                   signal_time, future_bars, spread_pips=1.5,
                   pip=0.0001, path_rule="pessimistic") -> Dict:
    TOL = 1e-12
    action = str(action).upper()
    if action not in ("BUY", "SELL"):
        return _result("INVALID", "NONE", 0.0, signal_time, entry, 0)

    spread_px = (spread_pips or 0.0) * pip

    def buy_hits(h, l):
        return (l <= sl - spread_px + TOL,
                h >= tp1 + spread_px - TOL,
                h >= tp2 + spread_px - TOL,
                h >= tp3 + spread_px - TOL)

    def sell_hits(h, l):
        return (h >= sl + spread_px - TOL,
                l <= tp1 - spread_px + TOL,
                l <= tp2 - spread_px + TOL,
                l <= tp3 - spread_px + TOL)

    rows = future_bars if isinstance(future_bars, list) else []
    # Support DataFrame too (duck typing)
    try:
        rows = [{"time": idx, "high": float(row["high"]), "low": float(row["low"]),
                 "close": float(row["close"])}
                for idx, row in future_bars.iterrows()]
    except AttributeError:
        pass

    for bar in rows:
        t = bar["time"]; h = bar["high"]; l = bar["low"]
        hits_fn = buy_hits if action == "BUY" else sell_hits
        sl_hit, tp1_hit, tp2_hit, tp3_hit = hits_fn(h, l)
        any_tp = tp1_hit or tp2_hit or tp3_hit
        mins = _mins(t, signal_time)

        if sl_hit and any_tp:
            if path_rule == "strict":
                return _result("AMBIG", "AMBIG", 0.0, t, entry, mins)
            if path_rule == "pessimistic":
                return _result("LOSS", "SL", -1.0, t, sl, mins)
            # optimistic — fall through to TP checks

        if sl_hit and not any_tp:
            return _result("LOSS", "SL", -1.0, t, sl, mins)
        if tp3_hit: return _result("WIN", "TP3", 3.0, t, tp3, mins)
        if tp2_hit: return _result("WIN", "TP2", 2.0, t, tp2, mins)
        if tp1_hit: return _result("WIN", "TP1", 1.0, t, tp1, mins)

    if rows:
        last = rows[-1]
        return _result("NONE", "NONE", 0.0, last["time"], last["close"],
                       _mins(last["time"], signal_time))
    return _result("NONE", "NONE", 0.0, signal_time, entry, 0)

def _mins(a, b) -> int:
    try: return int((a - b).total_seconds() / 60)
    except: return 0

def _result(outcome, hit, R, t, px, mins) -> Dict:
    return {"outcome": outcome, "hit_level": hit, "R_multiple": float(R),
            "exit_time": t, "exit_price": float(px), "duration_minutes": int(mins)}

def pip_size_for(pair: str) -> float:
    return 0.01 if str(pair).upper().endswith("JPY") else 0.0001

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="signals.csv")
    ap.add_argument("--out",     default="trades.csv")
    ap.add_argument("--horizon", type=int, default=96)
    ap.add_argument("--pair",    default="EURUSD")
    ap.add_argument("--tf",      default="M15")
    args = ap.parse_args()

    signals_path = os.path.expanduser(f"~/BotA/{args.signals}")
    out_path     = os.path.expanduser(f"~/BotA/{args.out}")

    rows = []
    with open(signals_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items()}
            ts = _parse_ts(row.get("timestamp", ""))
            if ts: row["_ts"] = ts; rows.append(row)

    results = []
    for row in rows:
        action = str(row.get("action", "WAIT")).upper()
        if action not in ("BUY", "SELL"): continue
        pair = str(row.get("pair", args.pair)).upper()
        tf   = str(row.get("tf",   args.tf)).upper()
        try:
            entry = float(row["entry_price"])
            sl    = float(row["stop_loss"])
            tp1   = float(row["tp1"])
            tp2   = float(row["tp2"])
            tp3   = float(row["tp3"])
        except Exception: continue

        bars = fetch_future_bars(pair, tf, row["_ts"], args.horizon)
        res  = simulate_trade(action, entry, sl, tp1, tp2, tp3,
                              row["_ts"], bars or [],
                              pip=pip_size_for(pair))
        results.append({**row, **res})

    for r in results: r.pop("_ts", None)
    if not results:
        print("[auditor] No results."); return

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()), extrasaction="ignore")
        writer.writeheader(); writer.writerows(results)

    wins   = sum(1 for r in results if r.get("outcome") == "WIN")
    losses = sum(1 for r in results if r.get("outcome") == "LOSS")
    wr = round(wins/(wins+losses)*100,1) if wins+losses else 0
    print(f"[auditor] {len(results)} trades → {out_path} | WR={wr}% ({wins}W/{losses}L)")

if __name__ == "__main__":
    main()
