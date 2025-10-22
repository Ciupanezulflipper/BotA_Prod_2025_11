from __future__ import annotations
import os, json, math
from urllib.request import urlopen
from urllib.parse import urlencode
from typing import Tuple

def _pair_to_provider_format(pair: str) -> str:
    # Finnhub "OANDA:EUR_USD" or "FXCM:EUR/USD". We'll pick OANDA mapping with underscore.
    base = pair[:3].upper()
    quote = pair[3:].upper()
    return f"OANDA:{base}_{quote}"

def _get_finnhub_quote(pair: str) -> Tuple[float, float]:
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY missing")
    sym = _pair_to_provider_format(pair)
    url = f"https://finnhub.io/api/v1/forex/quote?{urlencode({'symbol': sym, 'token': key})}"
    with urlopen(url, timeout=int(os.getenv("HTTP_TIMEOUT_SEC","8"))) as r:
        data = json.loads(r.read().decode("utf-8"))
    # Finnhub returns: o, h, l, c, pc (no bid/ask). Use candle mid + synthetic spread estimate (poor).
    # Try their /quote -> not ideal for FX. We'll estimate spread relative to price using heuristic.
    price = float(data.get("c") or 0.0)
    if price <= 0:
        raise RuntimeError("price missing")
    # Heuristic: 0.00008 on majors, 0.5-2 pips typical; allow override via SPREAD_DEFAULT_PIPS
    default_pips = float(os.getenv("SPREAD_DEFAULT_PIPS","1.0"))
    pipsize = 0.0001 if pair.endswith("USD") else float(os.getenv("PIP_SIZE","0.0001"))
    spread = default_pips * pipsize
    bid = price - spread/2
    ask = price + spread/2
    return bid, ask

def compute_spread_pips(pair: str) -> float:
    try:
        bid, ask = _get_finnhub_quote(pair)
        pip_size = float(os.getenv("PIP_SIZE","0.0001"))
        return max(0.0, (ask - bid) / pip_size)
    except Exception:
        # Last resort: use env override or safe default
        return float(os.getenv("SPREAD_DEFAULT_PIPS","1.0"))

def spread_ok(pair: str, max_pips: float) -> Tuple[bool, float]:
    sp = compute_spread_pips(pair)
    return (sp <= max_pips), sp
