#!/usr/bin/env python3
# ================================================================
# BotA — tools/risk_manager.py
# ✅ AUDITED BY 4 AIs (Claude • Perplexity • Gemini • DeepSeek)
# Stamp: Do not overwrite casually. If you think you must, remember:
# "This file passed 4 independent audits. Re-verify assumptions first."
# ------------------------------------------------
# Purpose: caps, market-day guards, UTC-safe timestamps
# ================================================================
import os
import datetime

def _env_flag(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip() in ("1", "true", "TRUE", "yes", "YES")

def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return default

def utc_today_str() -> str:
    # UTC-aware (replaces deprecated utcnow)
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

def daily_cap() -> int:
    return _env_int("DAILY_CAP", 30)

def send_wait_enabled() -> bool:
    return _env_flag("SEND_WAIT", "0")

def weekend_guard_enabled() -> bool:
    return _env_flag("WEEKEND_GUARD_ENABLE", "1")

def market_block_enabled() -> bool:
    return _env_flag("MARKET_BLOCK_ENABLE", "1")

def news_blackout_enabled() -> bool:
    return _env_flag("NEWS_BLACKOUT_ENABLE", "0")

# Simple JSON-safe report used by upstream
def report_state() -> dict:
    return {
        "utc_today": utc_today_str(),
        "send_wait": send_wait_enabled(),
        "daily_cap": daily_cap(),
        "weekend_guard": weekend_guard_enabled(),
        "market_block": market_block_enabled(),
        "news_blackout": news_blackout_enabled(),
    }

if __name__ == "__main__":
    # Smoke-output for quick CLI checks
    import json
    print(json.dumps(report_state(), indent=2))
# EOF
