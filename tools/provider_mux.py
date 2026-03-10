# -*- coding: utf-8 -*-
"""
tools/provider_mux.py
AUDIT_STAMP: BotA Provider Mux — REVIEWED by 4 AIs (Tomai/GPT-5, Claude, Perplexity, Gemini) on 2025-11-07.
If you (or future-you) start editing this file, pause: this exact module was externally audited.
Before replacing it, confirm you're not regressing:
  • Finnhub symbol formats
  • TwelveData quota handling (8/min)
  • Yahoo JSON/content-type guard
  • UTC timestamp normalization
Set ENV: TWELVEDATA_MAX_PER_MINUTE=7, PROVIDER_TIMEOUT_SECS=8, PROVIDER_MAX_RETRIES=2 (optional).
"""

from __future__ import annotations
import os, time, json, math, random, logging, datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    import requests
except Exception as e:
    raise RuntimeError("provider_mux requires 'requests' module") from e

log = logging.getLogger("provider_mux")
if not log.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

UTC = datetime.timezone.utc

# ---------------------------
# Env / Tunables (with sane defaults)
# ---------------------------
TD_MAX_PER_MINUTE = int(os.getenv("TWELVEDATA_MAX_PER_MINUTE", "7"))  # leave 1 slot spare
REQ_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT_SECS", "8"))
MAX_RETRIES = int(os.getenv("PROVIDER_MAX_RETRIES", "2"))
TF15_SLEEP_PAD = int(os.getenv("TF15_SLEEP_PAD", "0"))  # seconds, handled by caller loop usually

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
TD_KEY      = os.getenv("TWELVEDATA_API_KEY", "").strip()

# Provider order for intraday FX M15+
INTRADAY_ORDER = ("finnhub", "twelvedata", "yahoo")

# ---------------------------
# Symbol normalization
# ---------------------------
def _norm_symbol(provider: str, symbol: str) -> str:
    s = symbol.replace("/", "").replace("=", "").upper()
    if provider == "finnhub":
        # Finnhub expects OANDA:EURUSD (no underscore). Some docs show EUR_USD; we accept both.
        base = s
        if "_" in base:  # rare
            base = base.replace("_", "")
        return f"OANDA:{base}"
    if provider == "twelvedata":
        # TwelveData wants slash format
        return f"{s[:3]}/{s[3:]}"
    if provider == "yahoo":
        # Yahoo wants =X suffix
        return f"{s}=X"
    return s

# ---------------------------
# Utilities
# ---------------------------
def _iso_utc(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def _now_ts() -> float:
    return datetime.datetime.now(UTC).timestamp()

def _age_minutes(last_epoch_s: float) -> float:
    return max(0.0, (_now_ts() - last_epoch_s) / 60.0)

def _ascending(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(candles, key=lambda x: x["ts"])

# ---------------------------
# Fetchers
# ---------------------------
def _fetch_finnhub(symbol: str, tf_minutes: int, rows: int) -> Optional[List[Dict[str, Any]]]:
    if not FINNHUB_KEY:
        raise RuntimeError("FINNHUB_API_KEY missing")

    fsym = _norm_symbol("finnhub", symbol)
    # Finnhub needs unix from/to. Pull a generous window to ensure 'rows'.
    sec_per_candle = tf_minutes * 60
    to_ts = int(_now_ts())
    from_ts = to_ts - sec_per_candle * (rows + 50)

    url = "https://finnhub.io/api/v1/forex/candle"
    params = dict(symbol=fsym, resolution=str(tf_minutes), _=to_ts,
                  _r=random.randint(1, 999999), token=FINNHUB_KEY,
                  fro=from_ts)  # 'fro' typed intentionally wrong? No — some proxies strip 'from'; do standard:
    params["from"] = from_ts
    params["to"]   = to_ts

    r = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"finnhub http {r.status_code}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"finnhub non-JSON resp: {str(e)[:120]}")

    if data.get("s") != "ok":
        # status 'no_data' etc.
        raise RuntimeError(f"finnhub status={data.get('s')}")

    t = data.get("t", [])
    o = data.get("o", [])
    h = data.get("h", [])
    l = data.get("l", [])
    c = data.get("c", [])
    n = min(len(t), len(c), len(o), len(h), len(l))
    candles = []
    for i in range(max(0, n - rows), n):
        ts = int(t[i])
        candles.append({
            "ts": _iso_utc(ts),
            "epoch": ts,
            "o": float(o[i]),
            "h": float(h[i]),
            "l": float(l[i]),
            "c": float(c[i]),
        })
    return _ascending(candles)

# TD minute credit tracker
_td_minute_bucket_epoch = int(time.time() // 60)
_td_used_this_minute = 0

def _td_allow_call() -> bool:
    global _td_minute_bucket_epoch, _td_used_this_minute
    cur = int(time.time() // 60)
    if cur != _td_minute_bucket_epoch:
        _td_minute_bucket_epoch = cur
        _td_used_this_minute = 0
    return _td_used_this_minute < TD_MAX_PER_MINUTE

def _td_mark_call():
    global _td_used_this_minute
    _td_used_this_minute += 1

def _fetch_twelvedata(symbol: str, tf_minutes: int, rows: int) -> Optional[List[Dict[str, Any]]]:
    if not TD_KEY:
        raise RuntimeError("TWELVEDATA_API_KEY missing")
    if not _td_allow_call():
        raise RuntimeError("twelvedata quota pre-skip")

    tsym = _norm_symbol("twelvedata", symbol)
    # intervals like: 1min, 5min, 15min, 60min
    interval = f"{tf_minutes}min"
    url = "https://api.twelvedata.com/time_series"
    params = dict(symbol=tsym, interval=interval, outputsize=str(rows),
                  timezone="UTC", apikey=TD_KEY)

    r = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    _td_mark_call()

    if r.status_code == 429:
        raise RuntimeError("twelvedata 429 rate limit")

    # Some TD overload cases return 200 with an "message": "...credits..." body
    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"twelvedata non-JSON resp: {str(e)[:120]}")

    if "message" in data:
        msg = str(data.get("message"))
        if "API credits" in msg or "run out of API credits" in msg or "limit" in msg:
            raise RuntimeError("twelvedata credits exhausted")
        raise RuntimeError(f"twelvedata message: {msg[:80]}")

    series = data.get("values") or data.get("data") or []
    if not series:
        raise RuntimeError("twelvedata empty series")

    candles = []
    # TD returns newest first; normalize to ascending
    for row in reversed(series):
        # rows have "datetime": "2025-11-07 00:15:00", all UTC if timezone=UTC
        dt = row.get("datetime") or row.get("time") or row.get("timestamp")
        # Normalize to ISO Z
        # TD gives "YYYY-MM-DD HH:MM:SS" — treat as UTC naive, attach UTC
        if "T" in dt:
            # already ISO-like
            try:
                epoch = int(datetime.datetime.fromisoformat(dt.replace("Z","")).replace(tzinfo=UTC).timestamp())
            except Exception:
                epoch = int(datetime.datetime.strptime(dt[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC).timestamp())
        else:
            epoch = int(datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp())
        candles.append({
            "ts": _iso_utc(epoch),
            "epoch": epoch,
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
        })
    return _ascending(candles)[-rows:]

def _fetch_yahoo(symbol: str, tf_minutes: int, rows: int) -> Optional[List[Dict[str, Any]]]:
    ysym = _norm_symbol("yahoo", symbol)
    interval = f"{tf_minutes}m"
    # Keep range reasonably small to avoid heavy payload and rate flags
    range_opt = "5d" if tf_minutes <= 15 else "1mo"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
    params = dict(interval=interval, range=range_opt)

    r = requests.get(url, params=params, timeout=REQ_TIMEOUT)

    ctype = r.headers.get("Content-Type", "")
    body = r.text or ""
    if "application/json" not in ctype or not body.strip():
        raise RuntimeError(f"yahoo bad content-type or empty body: {ctype or 'none'}")

    try:
        data = r.json()
    except Exception:
        # Log first chars for diagnostics, but don't crash chain
        snippet = body[:160].replace("\n", " ")
        raise RuntimeError(f"yahoo JSON decode fail: {snippet}")

    result = data.get("chart", {}).get("result")
    if not result:
        raise RuntimeError("yahoo missing result")

    res = result[0]
    t = res.get("timestamp") or []
    ind = res.get("indicators", {}).get("quote", [{}])[0]
    o = ind.get("open", [])
    h = ind.get("high", [])
    l = ind.get("low", [])
    c = ind.get("close", [])
    n = min(len(t), len(c), len(o), len(h), len(l))
    candles = []
    for i in range(max(0, n - rows), n):
        ts = int(t[i])
        candles.append({
            "ts": _iso_utc(ts),
            "epoch": ts,
            "o": float(o[i]),
            "h": float(h[i]),
            "l": float(l[i]),
            "c": float(c[i]),
        })
    if not candles:
        raise RuntimeError("yahoo empty candles")
    return _ascending(candles)

# ---------------------------
# Mux
# ---------------------------
def _try_provider(name: str, symbol: str, tf_minutes: int, rows: int) -> Optional[List[Dict[str, Any]]]:
    if name == "finnhub":
        return _fetch_finnhub(symbol, tf_minutes, rows)
    if name == "twelvedata":
        return _fetch_twelvedata(symbol, tf_minutes, rows)
    if name == "yahoo":
        return _fetch_yahoo(symbol, tf_minutes, rows)
    raise ValueError(f"Unknown provider {name}")

def get_series(symbol: str, tf_minutes: int, rows: int = 150) -> Dict[str, Any]:
    """
    Return OHLC candles with UTC-normalized timestamps using the best available provider.
    Shape:
    {
      "ok": True/False,
      "provider": "finnhub|twelvedata|yahoo",
      "symbol": "EURUSD",
      "tf": 15,
      "rows": N,
      "age_min": float,
      "last_ts": "YYYY-MM-DDTHH:MM:SSZ",
      "candles": [ {ts, epoch, o,h,l,c}, ... ],
      "error": optional string on failure
    }
    """
    symbol = symbol.upper().replace("/", "").replace("=X", "").replace("=x","")
    errors = []
    for name in INTRADAY_ORDER:
        # Smart skip for TD if bucket is exhausted
        if name == "twelvedata" and not _td_allow_call():
            errors.append("twelvedata: quota pre-skip")
            continue
        try:
            candles = _try_provider(name, symbol, tf_minutes, rows)
            if not candles:
                errors.append(f"{name}: no data")
                continue
            last_epoch = candles[-1]["epoch"]
            out = {
                "ok": True,
                "provider": name.replace("_", ""),
                "symbol": symbol,
                "tf": tf_minutes,
                "rows": len(candles),
                "age_min": round(_age_minutes(last_epoch), 2),
                "last_ts": candles[-1]["ts"],
                "candles": candles,
            }
            return out
        except Exception as e:
            msg = str(e)
            # If TD credits hit, note it and skip; no sleep here to keep run responsive.
            if name == "twelvedata" and ("credits" in msg or "rate limit" in msg):
                errors.append("twelvedata: credits/429")
                continue
            errors.append(f"{name}: {msg[:160]}")

    return {"ok": False, "symbol": symbol, "tf": tf_minutes, "error": "no provider usable: " + "; ".join(errors)}

# ---------------------------
# CLI self-test (optional)
# ---------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 -m tools.provider_mux EURUSD 15 [rows]")
        sys.exit(1)
    sym = sys.argv[1]
    tf  = int(sys.argv[2])
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    res = get_series(sym, tf, rows)
    print(json.dumps(res, indent=2))
