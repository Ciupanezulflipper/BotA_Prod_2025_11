#!/usr/bin/env python3
import os, sys, json, argparse, importlib, pathlib
from typing import Dict, Any, List, Tuple, Optional

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from indicators import ema, rsi

NAME_MAP = {
    "yahoo": "data_provider_yahoo",
    "alpha_vantage": "data_provider_alphavantage",
    "alpha": "data_provider_alphavantage",
    "twelve_data": "data_provider_twelvedata",
    "twelvedata": "data_provider_twelvedata",
}

def _env_int(k: str, d: int) -> int:
    try:
        return int(os.getenv(k, d))
    except Exception:
        return d

def _env_float(k: str, d: float) -> float:
    try:
        return float(os.getenv(k, d))
    except Exception:
        return d

def _env_bool(k: str, d: bool = False) -> bool:
    v = str(os.getenv(k, str(d))).strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def _load_provider(name: str):
    mod_name = NAME_MAP.get(name.strip().lower(), name.strip().lower())
    return importlib.import_module(mod_name)

def _clamp_age_minutes(v) -> float:
    try:
        a = float(v)
    except Exception:
        a = 1e9
    if a < 0:
        a = 0.0
    return a

def _normalize_result(raw: Dict[str, Any], provider_name: str) -> Dict[str, Any]:
    rows = int(raw.get("rows", 0) or 0)
    age_min = _clamp_age_minutes(raw.get("age_min", 1e9))
    candles = raw.get("candles") or raw.get("bars") or raw.get("data") or []
    last_ts = raw.get("last_ts") or raw.get("last") or None
    return {
        "ok": bool(raw.get("ok", False)),
        "provider": provider_name,
        "rows": rows,
        "age_min": age_min,
        "last_ts": last_ts,
        "candles": candles,
        "error": raw.get("error"),
        "msg": raw.get("msg"),
    }

def pick_provider(symbol: str, tf: str, limit: int, providers: List[str], min_bars: int, max_age: float) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    failures: List[str] = []
    for pname in providers:
        try:
            mod = _load_provider(pname)
        except Exception as e:
            failures.append(f"{pname}: import fail {e}")
            continue
        try:
            res = mod.fetch(symbol, tf, limit)
        except Exception as e:
            failures.append(f"{pname}: exception {e}")
            continue
        if not isinstance(res, dict):
            failures.append(f"{pname}: bad type {type(res)}")
            continue
        norm = _normalize_result(res, pname)
        if not norm.get("ok"):
            failures.append(f"{pname}: {norm.get('error') or 'not ok'}")
            continue
        if norm["rows"] < min_bars:
            failures.append(f"{pname}: rows {norm['rows']} < {min_bars}")
            continue
        if norm["age_min"] > max_age:
            failures.append(f"{pname}: stale {norm['age_min']:.1f}m > {max_age:.1f}m")
            continue
        return norm, None
    return None, "; ".join(failures)

def compute_signal(candles: List[dict]) -> Dict[str, Any]:
    """
    Returns a schema-stable dict with keys:
      decision, score, ema_fast, ema_slow, rsi, price
    price is None if no closes were available.
    """
    closes: List[float] = []
    for c in candles:
        if isinstance(c, dict):
            close = c.get("c") or c.get("close") or c.get("Close")
        elif isinstance(c, (list, tuple)) and len(c) >= 5:
            close = c[4]
        else:
            close = None
        if close is None:
            continue
        try:
            closes.append(float(close))
        except Exception:
            continue

    # Guarantee schema: always include "price"
    price_val: Optional[float] = closes[-1] if closes else None

    if len(closes) < 30:
        return {
            "decision": "WAIT",
            "score": 0,
            "ema_fast": None,
            "ema_slow": None,
            "rsi": None,
            "price": price_val,  # schema-stable (DeepSeek finding)
            "reason": "insufficient_closes",
        }

    ema_fast_series = ema(closes, 9)
    ema_slow_series = ema(closes, 21)
    rsi_series = rsi(closes, 14)

    price = closes[-1]
    efast = ema_fast_series[-1]
    eslow = ema_slow_series[-1]
    r = rsi_series[-1]

    # Scoring: EMA distance + RSI distance from 50 (simple & bounded)
    ema_dist = (efast - eslow) / price * 1000.0  # scaled
    rsi_bias = r - 50.0
    base = abs(ema_dist) * 2.0 + abs(rsi_bias) * 1.2
    score = max(0, min(100, int(base)))

    decision = "WAIT"
    if efast > eslow and r >= 55:
        decision = "BUY"
    elif efast < eslow and r <= 45:
        decision = "SELL"

    return {
        "decision": decision,
        "score": score,
        "ema_fast": round(efast, 6),
        "ema_slow": round(eslow, 6),
        "rsi": round(r, 2),
        "price": round(price, 6),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", required=True)          # e.g. "15"
    ap.add_argument("--limit", type=int, default=150)
    args = ap.parse_args()

    order_raw = os.getenv("PROVIDER_ORDER", "twelve_data,alpha_vantage,yahoo")
    providers = [p.strip() for p in order_raw.split(",") if p.strip()] or ["twelve_data","alpha_vantage","yahoo"]

    min_bars = _env_int("MIN_BARS_REQUIRED", 120)
    max_age  = _env_float("MAX_DATA_AGE_MINUTES", 30.0)

    weak_mode  = _env_bool("WEAK_SIGNAL_MODE", True)   # preserved for compatibility
    dry_mode   = _env_bool("DRY_RUN_MODE", True)
    weak_th    = _env_int("WEAK_SIGNAL_THRESHOLD", 50)
    full_th    = _env_int("FULL_SIGNAL_THRESHOLD", 60)

    pick, err = pick_provider(args.symbol, args.tf, args.limit, providers, min_bars, max_age)
    if not pick:
        print(json.dumps({"ok": False, "error": f"no provider usable: {err}"}))
        sys.exit(0)

    candles = pick.get("candles") or []
    if not isinstance(candles, list) or not candles:
        print(json.dumps({"ok": False, "error": "no candle data received"}))
        sys.exit(0)

    try:
        sig = compute_signal(candles)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"signal computation failed: {e}"}))
        sys.exit(0)

    decision = sig.get("decision", "WAIT")
    score = int(sig.get("score", 0) or 0)

    is_weak = False
    if decision in ("BUY","SELL"):
        if score < weak_th:
            decision = "WAIT"
        elif score < full_th:
            is_weak = True

    out = {
        "ok": True,
        "provider": pick.get("provider"),
        "symbol": args.symbol,
        "tf": str(args.tf),
        "rows": pick.get("rows"),
        "age_min": pick.get("age_min"),
        "last_ts": pick.get("last_ts"),
        "decision": decision,
        "score": score,
        "weak": bool(is_weak),
        "dry_run": bool(dry_mode),
        "indicators": {
            "ema_fast": sig.get("ema_fast"),
            "ema_slow": sig.get("ema_slow"),
            "rsi": sig.get("rsi"),
            "price": sig.get("price"),   # now always present (may be None)
        },
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)

if __name__ == "__main__":
    main()
