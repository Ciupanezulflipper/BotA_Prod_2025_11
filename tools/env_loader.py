"""
Bot A • Environment Loader (authoritative)

- Loads .env.runtime or .env from standard locations
- Normalizes all key names so every module sees them
- Sets sane defaults for provider order and rate limits
"""

from __future__ import annotations
import os, pathlib
from typing import Iterable

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # fallback: rely on existing env

# --------------------- file candidates ---------------------
CANDIDATES = [
    pathlib.Path.cwd() / ".env.runtime",
    pathlib.Path.cwd() / ".env",
    pathlib.Path.home() / "bot-a" / ".env.runtime",
    pathlib.Path.home() / "BotA" / ".env.runtime",
    pathlib.Path.home() / ".env.runtime",
    pathlib.Path.home() / ".env",
]

def _load_first() -> str | None:
    if load_dotenv is None:
        return None
    for p in CANDIDATES:
        try:
            if p.exists():
                ok = load_dotenv(p, override=False)
                if ok:
                    return str(p)
        except Exception:
            pass
    return None

def _alias(dst: str, sources: Iterable[str]):
    """If dst unset, copy from first nonempty in sources"""
    if os.environ.get(dst):
        return
    for s in sources:
        v = os.environ.get(s, "").strip()
        if v:
            os.environ[dst] = v
            return

def _normalize():
    # TwelveData
    _alias("TWELVEDATA_API_KEY",
           ("TWELVE_DATA_API_KEY", "TWELVEDATA_KEY", "TWELVEDATA_TOKEN", "TWELVE_API_KEY"))
    _alias("TWELVE_DATA_API_KEY", ("TWELVEDATA_API_KEY",))
    _alias("TWELVEDATA_KEY", ("TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY"))
    _alias("TWELVEDATA_TOKEN", ("TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY"))

    # AlphaVantage
    _alias("ALPHAVANTAGE_API_KEY",
           ("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_KEY", "AV_KEY"))
    _alias("ALPHA_VANTAGE_API_KEY", ("ALPHAVANTAGE_API_KEY",))
    _alias("ALPHAVANTAGE_KEY", ("ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY"))
    _alias("AV_KEY", ("ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY"))

    # Finnhub
    _alias("FINNHUB_API_KEY", ("FINNHUB_KEY", "FH_KEY"))

    # Provider order
    if not os.environ.get("PROVIDER_ORDER"):
        os.environ["PROVIDER_ORDER"] = "twelvedata,alphavantage"

def _sanity_check_flags():
    # avoid rate-limit spam
    os.environ.setdefault("TWELVEDATA_RATE_PER_MIN", "1")
    os.environ.setdefault("ALPHAVANTAGE_RATE_PER_MIN", "0")
    os.environ.setdefault("EODHD_RATE_PER_MIN", "0")
    os.environ.setdefault("YAHOO_RATE_PER_MIN", "0")

# -------------------- run immediately ----------------------
_loaded = _load_first()
_normalize()
_sanity_check_flags()

os.environ["BOTA_ENV_LOADER_STATUS"] = f"ok:{bool(_loaded)}"
