
#!/usr/bin/env python3

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import pandas as pd


# ---------- Provider fetch ----------

def _fetch_rows(pair: str, tf: str, bars: int) -> Tuple[pd.DataFrame, str]:
    """
    Get OHLC rows + provider source. Supports either get_ohlc() or fetch_ohlc().
    Returns a normalized DataFrame with ['time','open','high','low','close','volume'].
    """
    rows: Optional[list] = None
    source = "unknown"

    # Try get_ohlc(pair, tf, bars) -> (rows, source)
    try:
        from BotA.tools.providers import get_ohlc  # type: ignore
        res = get_ohlc(pair, tf, bars)
        if isinstance(res, tuple) and len(res) == 2:
            rows, source = res
    except Exception:
        pass

    # Fallback fetch_ohlc(pair, tf, bars) -> rows  (maybe also returns (rows, source))
    if rows is None:
        try:
            from BotA.tools.providers import fetch_ohlc  # type: ignore
            res = fetch_ohlc(pair, tf, bars)
            if isinstance(res, tuple) and len(res) == 2:
                rows, source = res
            else:
                rows = res
        except Exception as e:
            print(f"✗ Data fetch failed: {e}")
            sys.exit(1)

    if not rows:
        print(f"✗ No data returned for {pair} {tf}")
        sys.exit(1)

    # Normalize to DataFrame with lowercase cols
    df = pd.DataFrame(rows)
    df.columns = [str(c).strip().lower() for c in df.columns]
    # Harmonize common variants
    colmap = {
        "timestamp": "time",
        "date": "time",
        "datetime": "time",
        "ohlc_time": "time",
    }
    df.rename(columns={k: v for k, v in colmap.items() if k in df.columns}, inplace=True)

    required = {"time", "open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        raise SystemExit("✗ providers: missing required OHLC columns after normalization")

    # Ensure types
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df.dropna(subset=["time", "open", "high", "low", "close"], inplace=True)
    return df.reset_index(drop=True), source


# ---------- Indicators / scoring hooks ----------

def _analyze_indicators(df: pd.DataFrame, pair: str) -> Dict[str, Any]:
    """
    Calls your existing indicators_ext.analyze_indicators(df, pair).
    Returns a dict (may be partially filled).
    """
    try:
        from BotA.tools.indicators_ext import analyze_indicators  # type: ignore
        return analyze_indicators(df, pair) or {}
    except Exception as e:
        print(f"⚠ Indicator analysis failed: {e}")
        return {}


def _try_compute_scores(df: pd.DataFrame, pair: str, tf: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Try several known score engines and return (score16, score6) if available.
    Works even if function names differ a bit across versions.
    """
    candidates = [
        ("BotA.tools.scoring_v2", ["compute_scores", "score_all", "score_confluence", "score"]),
        ("BotA.tools.scoring",    ["compute_scores", "score_all", "score"]),
        ("BotA.tools.tf_confluence", ["compute_scores", "score_all", "score"]),
    ]
    for mod_name, fn_names in candidates:
        try:
            mod = __import__(mod_name, fromlist=["*"])
        except Exception:
            continue
        for fn_name in fn_names:
            fn = getattr(mod, fn_name, None)
            if not callable(fn):
                continue
            try:
                # Try kwargs first, then positional
                try:
                    res = fn(df=df, pair=pair, tf=tf)  # type: ignore
                except Exception:
                    res = fn(df, pair, tf)  # type: ignore

                # Accept dict or tuple
                if isinstance(res, dict):
                    s16 = res.get("score16") or res.get("score_16") or res.get("s16")
                    s6 = res.get("score6") or res.get("score_6") or res.get("s6")
                    if s16 is not None or s6 is not None:
                        return s16, s6
                elif isinstance(res, tuple) and len(res) >= 2:
                    return res[0], res[1]
            except Exception:
                continue
    return None, None


# ---------- ATR & risk ----------

def _compute_atr(df: pd.DataFrame, period: int) -> float:
    """
    Average True Range in PRICE units (not pips).
    Rolling mean approximation of Wilder's smoothing.
    """
    if len(df) < period:
        raise ValueError(f"Need at least {period} bars for ATR({period}), got {len(df)}")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period, min_periods=period).mean()
    atr_values = atr.dropna()
    if len(atr_values) == 0:
        raise ValueError("ATR calculation produced no valid values")

    return float(atr_values.iloc[-1])


def _risk_targets(action: str, entry: float, atr: float, sl_mult: float, tp1_mult: float, tp2_mult: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if action.upper() == "BUY":
        out["sl"] = entry - sl_mult * atr
        out["tp1"] = entry + tp1_mult * atr
        out["tp2"] = entry + tp2_mult * atr
    elif action.upper() == "SELL":
        out["sl"] = entry + sl_mult * atr
        out["tp1"] = entry - tp1_mult * atr
        out["tp2"] = entry - tp2_mult * atr
    return out


# ---------- Spread / ticks / entry price ----------

def _get_provider_tick(pair: str) -> Optional[Dict[str, float]]:
    """
    Try to fetch a provider tick (bid/ask). Supports several possible function names.
    """
    names = ["get_tick", "get_current_tick", "fetch_tick", "get_quote", "last_tick"]
    try:
        prov = __import__("BotA.tools.providers", fromlist=["*"])
    except Exception:
        return None
    for nm in names:
        fn = getattr(prov, nm, None)
        if callable(fn):
            try:
                res = fn(pair)  # type: ignore
            except Exception:
                continue
            if isinstance(res, dict):
                # Expect keys like bid/ask or similar
                bid = res.get("bid") or res.get("Bid") or res.get("b")
                ask = res.get("ask") or res.get("Ask") or res.get("a")
                if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and ask > 0:
                    return {"bid": float(bid), "ask": float(ask)}
    return None


def _get_spread_pips(pair: str, tick: Optional[Dict[str, float]]) -> Tuple[Optional[float], str]:
    """
    Returns (spread_pips, source_label).
    SPREAD_SOURCE=auto|manual (default auto).
    - auto: use provider tick if available; else None
    - manual: use SPREAD_PIPS env
    """
    mode = os.getenv("SPREAD_SOURCE", "auto").lower()
    if mode == "manual":
        try:
            p = float(os.getenv("SPREAD_PIPS", "").strip())
            return p, "manual"
        except Exception:
            return None, "manual?"
    # auto
    if tick and "bid" in tick and "ask" in tick:
        # EURUSD pip = 0.0001
        pips = (tick["ask"] - tick["bid"]) / 0.0001
        return round(pips, 1), "auto"
    return None, "auto?"


def _best_entry_price(df: pd.DataFrame, pair: str) -> Tuple[float, str, Optional[Dict[str, float]]]:
    """
    Decide entry price:
      - ENTRY_SOURCE=manual → ENTRY_PRICE
      - ENTRY_SOURCE=mid (default) → midpoint if tick available; else close
      - ENTRY_SOURCE=close → last close
    Returns (entry_price, source_label, tick_if_any)
    """
    src = os.getenv("ENTRY_SOURCE", "mid").lower()
    if src == "manual":
        ep = float(os.getenv("ENTRY_PRICE", "nan"))
        if not (ep == ep):  # NaN check
            src = "close"
        else:
            return ep, "manual", None

    tick = _get_provider_tick(pair)
    last_close = float(df["close"].iloc[-1])

    if src == "mid":
        if tick:
            mid = (tick["bid"] + tick["ask"]) / 2.0
            return float(mid), "mid", tick
        return last_close, "close", None

    # src == "close"
    return last_close, "close", tick


# ---------- Rendering ----------

def _fmt_price(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{float(x):.5f}"


def _build_card(pair: str,
                tf: str,
                analysis: Dict[str, Any],
                score16: Optional[Any],
                score6: Optional[Any],
                entry: float,
                price_src: str,
                atr_val: Optional[float],
                targets: Dict[str, float],
                spread_pips: Optional[float],
                provider_source: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    action = str(analysis.get("action", "WAIT")).upper()
    reason = analysis.get("reason", "n/a")
    risk = analysis.get("risk", "normal")

    # Score text
    s16_txt = str(score16) if score16 is not None else "n/a"
    s6_txt = str(score6) if score6 is not None else "n/a"

    # Header
    lines = []
    lines.append(f"📊 {pair} ({tf})")
    lines.append(f"🕒 Signal Time: {now}")
    lines.append(f"📈 Action: {action}")
    lines.append(f"📊 Score: {s16_txt}/16 + {s6_txt}/6")
    lines.append(f"🧠 Reason: {reason}")
    lines.append(f"⚠️ Risk: {risk}")

    if spread_pips is None:
        lines.append(f"📉 Spread: n/a")
    else:
        lines.append(f"📉 Spread: {spread_pips:.1f} pips")

    # Risk & targets
    if atr_val is not None and action in ("BUY", "SELL"):
        lines.append("")
        lines.append("📐 Risk & Targets")
        lines.append(f"ATR(14): {_fmt_price(atr_val)}")
        lines.append(f"Entry:  {_fmt_price(entry)}")
        lines.append(f"SL:     {_fmt_price(targets.get('sl'))}")
        lines.append(f"TP1:    {_fmt_price(targets.get('tp1'))}  (1R)")
        lines.append(f"TP2:    {_fmt_price(targets.get('tp2'))}  (2R)")

    lines.append("")
    lines.append(f"Price source: {price_src}")
    lines.append(f"Source: {provider_source}")
    lines.append("")
    lines.append("Tip: use --dry-run to preview or --force to send.")

    return "\n".join(lines)


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="FX Confluence Signal Runner + ATR/Targets")
    parser.add_argument("--pair", required=True)
    parser.add_argument("--tf", required=True)
    parser.add_argument("--bars", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    pair = args.pair.upper()
    tf = args.tf.upper()
    bars = int(args.bars)
    force = bool(args.force)

    MIN_BARS = 120
    df, provider_source = _fetch_rows(pair, tf, bars)

    if len(df) < MIN_BARS and not force:
        print(f"✗ Insufficient data for {pair} {tf} (got {len(df)}, need ≥{MIN_BARS})")
        sys.exit(1)

    analysis = _analyze_indicators(df, pair)

    # Scores (attempt to compute via repo engines)
    s16, s6 = _try_compute_scores(df, pair, tf)

    # Entry price & spread
    entry_price, price_src, tick = _best_entry_price(df, pair)
    spread_pips, _spread_src = _get_spread_pips(pair, tick)

    # ATR & targets
    atr_period = int(os.getenv("ATR_PERIOD", "14"))
    sl_mult = float(os.getenv("ATR_SL_MULT", "1.5"))
    tp1_mult = float(os.getenv("ATR_TP1_MULT", "1.5"))
    tp2_mult = float(os.getenv("ATR_TP2_MULT", "3.0"))
    spread_atr_max = float(os.getenv("SPREAD_ATR_MAX", "0.35"))

    atr_val: Optional[float] = None
    targets: Dict[str, float] = {}

    try:
        atr_val = _compute_atr(df, atr_period)
        # Spread vs ATR quality gate (if both available)
        if spread_pips is not None and atr_val > 0:
            # Convert ATR (price) to pips for EURUSD
            atr_pips = atr_val / 0.0001
            ratio = spread_pips / atr_pips
            if ratio > spread_atr_max and not force:
                # Downgrade to WAIT if spread is too high
                analysis["action"] = "WAIT"
                analysis.setdefault("reason", "Spread too high relative to ATR")
        # Compute targets only if actionable
        if str(analysis.get("action", "WAIT")).upper() in ("BUY", "SELL") and atr_val is not None:
            targets = _risk_targets(str(analysis["action"]), entry_price, atr_val, sl_mult, tp1_mult, tp2_mult)
    except Exception as e:
        print(f"⚠ ATR/targets skipped: {e}")

    # Build card
    card = _build_card(
        pair=pair,
        tf=tf,
        analysis=analysis,
        score16=s16,
        score6=s6,
        entry=entry_price,
        price_src=price_src,
        atr_val=atr_val,
        targets=targets,
        spread_pips=spread_pips,
        provider_source=provider_source,
    )

    if args.dry_run:
        print(card)
        return

    # Send
    try:
        from BotA.tools.telegramalert import send_telegram_message  # type: ignore
    except Exception:
        print("✗ Cannot import telegramalert")
        sys.exit(1)
    ok, err = send_telegram_message(card)
    print("✓ Signal sent to Telegram" if ok else f"✗ Telegram send failed: {err}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
