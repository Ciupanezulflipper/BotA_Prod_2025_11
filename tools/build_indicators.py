#!/usr/bin/env python3
"""
FILE: tools/build_indicators.py

ROLE
- Load candle data from cache (JSON/CSV)
- Normalize into a standard internal candle list
- Compute indicators ONLY if timeframe is valid (fail-closed contract)

SAFETY RAIL (FAIL-CLOSED)
- HARD fail on timeframe mismatch to prevent M15 labels computed from H1/M5 data
- Always emits a stable JSON contract with required keys (even on failure)

OUTPUT CONTRACT (always present keys)
pair, timeframe, price, age_min, tf_ok, tf_actual_min, weak, error,
ema9, ema21, rsi, macd_hist, adx, atr, atr_pips

STDLIB ONLY
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {msg}", file=sys.stderr)


FUTURE_TS_CUTOFF_SEC = 4102444800  # 2100-01-01 UTC (approx)
DEFAULT_RSI = 50.0


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def _norm_ts(t: Any) -> Optional[int]:
    """
    Accepts epoch timestamps in seconds, milliseconds, or microseconds.
    Returns int seconds, or None if invalid/unreasonable.
    """
    try:
        if t is None:
            return None
        if isinstance(t, str):
            t = t.strip()
            if not t:
                return None
            if t.isdigit():
                t = int(t)
            else:
                return None

        if isinstance(t, float):
            if t != t:  # NaN
                return None
            t = int(t)

        if not isinstance(t, int):
            return None

        if t >= 100_000_000_000_000:
            t = int(t / 1_000_000)
        elif t >= 100_000_000_000:
            t = int(t / 1_000)

        if t <= 0:
            return None
        if t > FUTURE_TS_CUTOFF_SEC:
            return None
        return int(t)
    except Exception:
        return None


def tf_minutes(tf: str) -> int:
    tf = (tf or "").strip().upper()
    if tf.startswith("M"):
        try:
            return int(tf[1:])
        except Exception:
            return 0
    if tf.startswith("H"):
        try:
            return int(tf[1:]) * 60
        except Exception:
            return 0
    return 0


def _pip_size(pair: str, price: float) -> float:
    p = (pair or "").upper().strip()
    if p.endswith("JPY"):
        return 0.01
    if p in ("XAUUSD", "XAU/USD"):
        return 0.1
    if p in ("XAGUSD", "XAG/USD"):
        return 0.01
    if price > 500:
        return 1.0
    return 0.0001


def load_from_yahoo_chart(data: dict) -> List[Dict[str, float]]:
    try:
        r = data["chart"]["result"][0]
        ts = r.get("timestamp", []) or []
        q = (r.get("indicators", {}) or {}).get("quote", [{}])[0] or {}
        opens = q.get("open", []) or []
        highs = q.get("high", []) or []
        lows = q.get("low", []) or []
        closes = q.get("close", []) or []

        n = min(len(ts), len(opens), len(highs), len(lows), len(closes))
        out: List[Dict[str, float]] = []
        for i in range(n):
            t = _norm_ts(ts[i])
            o = _safe_float(opens[i])
            h = _safe_float(highs[i])
            l = _safe_float(lows[i])
            c = _safe_float(closes[i])
            if t is None or o is None or h is None or l is None or c is None:
                continue
            if c <= 0:
                continue
            out.append({"time": float(t), "open": o, "high": h, "low": l, "close": c})

        log(f"[indicators] Yahoo chart candles loaded: {len(out)} rows")
        return out
    except Exception as e:
        log(f"[indicators] Yahoo parse error: {e}")
        return []


def load_from_oanda_like(data: dict) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    try:
        candles = data.get("candles", [])
        if not isinstance(candles, list):
            return out
        for r in candles:
            if not isinstance(r, dict):
                continue
            t = _norm_ts(r.get("time") or r.get("timestamp"))
            if t is None:
                continue

            if "mid" in r and isinstance(r.get("mid"), dict):
                mid = r["mid"]
                o = _safe_float(mid.get("o"))
                h = _safe_float(mid.get("h"))
                l = _safe_float(mid.get("l"))
                c = _safe_float(mid.get("c"))
            else:
                o = _safe_float(r.get("open"))
                h = _safe_float(r.get("high"))
                l = _safe_float(r.get("low"))
                c = _safe_float(r.get("close"))

            if o is None or h is None or l is None or c is None:
                continue
            if c <= 0:
                continue
            out.append({"time": float(t), "open": o, "high": h, "low": l, "close": c})
        return out
    except Exception:
        return out


def load_from_json_generic(data: list) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for r in data:
        if not isinstance(r, dict):
            continue
        t = _norm_ts(r.get("time") or r.get("timestamp"))
        o = _safe_float(r.get("open"))
        h = _safe_float(r.get("high"))
        l = _safe_float(r.get("low"))
        c = _safe_float(r.get("close"))
        if t is None or o is None or h is None or l is None or c is None:
            continue
        if c <= 0:
            continue
        out.append({"time": float(t), "open": o, "high": h, "low": l, "close": c})
    return out


def load_from_csv(path: Path) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            rows = [r for r in reader if r and any(x.strip() for x in r)]
        if not rows:
            return out

        def _is_int_str(s: str) -> bool:
            s = (s or "").strip()
            return s.isdigit()

        start_idx = 1 if not _is_int_str(rows[0][0]) else 0

        for r in rows[start_idx:]:
            if len(r) < 5:
                continue
            t = _norm_ts(r[0])
            o = _safe_float(r[1])
            h = _safe_float(r[2])
            l = _safe_float(r[3])
            c = _safe_float(r[4])
            if t is None or o is None or h is None or l is None or c is None:
                continue
            if c <= 0:
                continue
            out.append({"time": float(t), "open": o, "high": h, "low": l, "close": c})
        return out
    except Exception as e:
        log(f"[indicators] CSV parse error: {e}")
        return out


def load_candles(path: Path) -> List[Dict[str, float]]:
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            c = load_from_yahoo_chart(data)
            if c:
                return c
            c = load_from_oanda_like(data)
            if c:
                return c
            return []
        if isinstance(data, list):
            return load_from_json_generic(data)
        return []
    except Exception:
        return load_from_csv(path)


def normalize_candles(candles: List[Dict[str, float]]) -> List[Dict[str, float]]:
    by_time: Dict[int, Dict[str, float]] = {}
    for c in candles:
        t = _norm_ts(c.get("time"))
        o = _safe_float(c.get("open"))
        h = _safe_float(c.get("high"))
        l = _safe_float(c.get("low"))
        cl = _safe_float(c.get("close"))
        if t is None or o is None or h is None or l is None or cl is None:
            continue
        if cl <= 0 or o <= 0 or h <= 0 or l <= 0:
            continue
        if h < l:
            continue
        by_time[int(t)] = {"time": float(int(t)), "open": o, "high": h, "low": l, "close": cl}

    out = list(by_time.values())
    out.sort(key=lambda x: int(x["time"]))
    return out


def validate_tf(candles: List[Dict[str, float]], tf: str, window: int = 200) -> Tuple[bool, float]:
    expected = tf_minutes(tf)
    if expected <= 0:
        return False, 0.0
    if len(candles) < 3:
        return False, 0.0

    c = candles[-window:] if len(candles) > window else candles
    if len(c) < 3:
        return False, 0.0

    deltas = []
    for i in range(1, len(c)):
        dt = int(c[i]["time"]) - int(c[i - 1]["time"])
        if dt > 0:
            deltas.append(dt)
    if not deltas:
        return False, 0.0

    median_sec = statistics.median(deltas)
    actual_min = float(median_sec) / 60.0

    low_ok = actual_min >= expected * 0.80
    high_ok = actual_min <= expected * 1.25
    return (low_ok and high_ok), actual_min


def ema_series(vals: List[float], p: int) -> List[float]:
    if not vals:
        return []
    k = 2.0 / (p + 1.0)
    out = [vals[0]]
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1.0 - k)
        out.append(e)
    return out


def rsi_wilder_last(closes: List[float], p: int = 14) -> float:
    n = len(closes)
    if n < p + 1:
        return DEFAULT_RSI

    gains = 0.0
    losses = 0.0
    for i in range(1, p + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses += -d

    avg_gain = gains / p
    avg_loss = losses / p

    for i in range(p + 1, n):
        d = closes[i] - closes[i - 1]
        gain = d if d > 0 else 0.0
        loss = (-d) if d < 0 else 0.0
        avg_gain = (avg_gain * (p - 1) + gain) / p
        avg_loss = (avg_loss * (p - 1) + loss) / p

    if avg_loss <= 1e-12:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_hist_last(closes: List[float]) -> float:
    if len(closes) < 35:
        return 0.0
    e12 = ema_series(closes, 12)
    e26 = ema_series(closes, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    signal = ema_series(macd, 9)
    return macd[-1] - signal[-1]


def atr_wilder_last(highs: List[float], lows: List[float], closes: List[float], p: int = 14) -> float:
    n = len(closes)
    if n < p + 1:
        return 0.0

    tr: List[float] = []
    for i in range(1, n):
        h = highs[i]
        l = lows[i]
        pc = closes[i - 1]
        tr_i = max(h - l, abs(h - pc), abs(l - pc))
        tr.append(tr_i)

    if len(tr) < p:
        return 0.0

    atr = sum(tr[:p]) / p
    for i in range(p, len(tr)):
        atr = (atr * (p - 1) + tr[i]) / p
    return atr


def adx_wilder_last(highs: List[float], lows: List[float], closes: List[float], p: int = 14) -> float:
    n = len(closes)
    if n < (2 * p + 1):
        return 0.0

    tr: List[float] = []
    pdm: List[float] = []
    ndm: List[float] = []

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        p_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        n_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        tr_i = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

        tr.append(tr_i)
        pdm.append(p_dm)
        ndm.append(n_dm)

    tr_s = sum(tr[:p])
    pdm_s = sum(pdm[:p])
    ndm_s = sum(ndm[:p])

    dx_list: List[float] = []

    for i in range(p, len(tr)):
        if i > p:
            tr_s = tr_s - (tr_s / p) + tr[i]
            pdm_s = pdm_s - (pdm_s / p) + pdm[i]
            ndm_s = ndm_s - (ndm_s / p) + ndm[i]

        if tr_s <= 1e-12:
            dx_list.append(0.0)
            continue

        pdi = 100.0 * (pdm_s / tr_s)
        ndi = 100.0 * (ndm_s / tr_s)
        den = pdi + ndi
        dx = 0.0 if den <= 1e-12 else 100.0 * (abs(pdi - ndi) / den)
        dx_list.append(dx)

    if len(dx_list) < p:
        return 0.0

    adx = sum(dx_list[:p]) / p
    for i in range(p, len(dx_list)):
        adx = (adx * (p - 1) + dx_list[i]) / p

    return adx


def build_bundle(pair: str, tf: str, candles_in: List[Dict[str, float]]) -> Dict[str, Any]:
    candles_n = normalize_candles(candles_in)

    ok, actual_min = validate_tf(candles_n, tf, window=200)

    price = float(candles_n[-1]["close"]) if candles_n else 0.0
    age_min = ((time.time() - float(candles_n[-1]["time"])) / 60.0) if candles_n else 0.0

    bundle: Dict[str, Any] = {
        "pair": pair,
        "timeframe": tf,
        "price": price,
        "age_min": age_min,
        "tf_ok": bool(ok),
        "tf_actual_min": float(actual_min),
        "weak": True,
        "error": "",
        "ema9": 0.0,
        "ema21": 0.0,
        "rsi": DEFAULT_RSI,
        "macd_hist": 0.0,
        "adx": 0.0,
        "atr": 0.0,
        "atr_pips": 0.0,
    }

    if not ok:
        bundle["error"] = "tf_mismatch"
        return bundle

    SAFE_WINDOW = 500
    if len(candles_n) > SAFE_WINDOW:
        candles_n = candles_n[-SAFE_WINDOW:]

    min_bars = 60
    if len(candles_n) < min_bars:
        bundle["error"] = "insufficient_data"
        return bundle

    closes = [float(c["close"]) for c in candles_n]
    highs = [float(c["high"]) for c in candles_n]
    lows = [float(c["low"]) for c in candles_n]

    e9 = ema_series(closes, 9)
    e21 = ema_series(closes, 21)

    bundle["ema9"] = float(e9[-1]) if e9 else 0.0
    bundle["ema21"] = float(e21[-1]) if e21 else 0.0
    bundle["rsi"] = float(rsi_wilder_last(closes, 14))
    bundle["macd_hist"] = float(macd_hist_last(closes))
    bundle["atr"] = float(atr_wilder_last(highs, lows, closes, 14))
    bundle["adx"] = float(adx_wilder_last(highs, lows, closes, 14))

    pip = _pip_size(pair, bundle["price"])
    bundle["atr_pips"] = float(bundle["atr"] / pip) if pip > 0 else 0.0

    bundle["weak"] = False
    bundle["error"] = ""
    return bundle


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    args = ap.parse_args()

    in_path = Path(args.inp)
    out_path = Path(args.outp)

    try:
        candles = load_candles(in_path)
    except Exception as e:
        log(f"[indicators] load_candles exception: {e}")
        candles = []

    bundle = build_bundle(args.pair, args.tf, candles)

    out_path.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
