"""
Boot the environment from .env.runtime, normalize key names,
then hand off to tools.runner_confluence as __main__.

Usage:
  python3 -m tools.boot_env -- --pair EURUSD --tf M15 --dry-run
"""
from __future__ import annotations
import os, sys, pathlib, runpy
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

CANDIDATES = [
    pathlib.Path.cwd() / ".env.runtime",
    pathlib.Path.cwd() / ".env",
    pathlib.Path.home() / "bot-a" / ".env.runtime",
    pathlib.Path.home() / "BotA" / ".env.runtime",
    pathlib.Path.home() / ".env.runtime",
    pathlib.Path.home() / ".env",
]

def _load_any() -> str | None:
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

def _alias(dst: str, *sources: str):
    if os.environ.get(dst):
        return
    for s in sources:
        v = os.environ.get(s)
        if v:
            os.environ[dst] = v
            return

def _normalize_env():
    # TwelveData
    _alias("TWELVEDATA_API_KEY",
           "TWELVE_DATA_API_KEY", "TWELVEDATA_KEY", "TWELVEDATA_TOKEN", "TWELVE_API_KEY")
    _alias("TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY")  # both ways
    # AlphaVantage
    _alias("ALPHAVANTAGE_API_KEY",
           "ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_KEY", "AV_KEY")
    _alias("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY")
    # Finnhub
    _alias("FINNHUB_API_KEY", "FINNHUB_KEY", "FH_KEY")
    # Provider order: keep simple and stable by default
    if not os.environ.get("PROVIDER_ORDER"):
        os.environ["PROVIDER_ORDER"] = "twelvedata"

def main():
    _load_any()
    _normalize_env()
    # Hand off CLI args to runner_confluence unchanged (after optional "--")
    if "--" in sys.argv:
        i = sys.argv.index("--")
        sys.argv = ["tools.runner_confluence"] + sys.argv[i+1:]
    else:
        sys.argv = ["tools.runner_confluence"] + sys.argv[1:]
    runpy.run_module("tools.runner_confluence", run_name="__main__")

if __name__ == "__main__":
    main()
