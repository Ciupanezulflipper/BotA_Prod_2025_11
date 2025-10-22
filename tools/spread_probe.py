from __future__ import annotations
import os, json
import requests

def _verify_flag() -> bool:
    # Respect ship/land mode: VERIFY_SSL=false disables cert checks
    return os.getenv("VERIFY_SSL", "true").lower() != "false"

def _pair_to_yahoo_symbol(pair: str) -> str:
    # EURUSD -> EURUSD=X
    p = pair.upper().replace("/", "")
    return f"{p}=X"

def get_spread_pips(pair: str) -> tuple[float | None, str]:
    """
    Try to get live spread in pips.
    Returns (spread_pips or None, source_string).
    Order:
      1) Yahoo Finance bid/ask
      2) SPREAD_PIPS_DEFAULT from .env
      3) None
    """
    # 1) Yahoo Finance quote
    try:
        sym = _pair_to_yahoo_symbol(pair)
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}"
        r = requests.get(url, timeout=6, verify=_verify_flag())
        r.raise_for_status()
        q = r.json()
        res = q.get("quoteResponse", {}).get("result", [])
        if res:
            ask = res[0].get("ask")
            bid = res[0].get("bid")
            if isinstance(ask, (int, float)) and isinstance(bid, (int, float)) and ask > 0 and bid > 0:
                # For EURUSD, pip factor = 10_000
                pip_factor = 10000.0
                return (max(0.0, (ask - bid) * pip_factor), "yahoo")
    except Exception:
        pass

    # 2) Env default
    try:
        env_val = os.getenv("SPREAD_PIPS_DEFAULT", "").strip()
        if env_val:
            return (float(env_val), "env")
    except Exception:
        pass

    # 3) Give up
    return (None, "none")
