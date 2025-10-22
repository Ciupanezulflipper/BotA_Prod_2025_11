#!/usr/bin/env python3
"""
API-aware circuit breaker for BotA
Tracks API usage and prevents quota exhaustion
"""

import os
import json
from datetime import datetime
from pathlib import Path

# API Limits (calls per day)
LIMITS = {
    "twelvedata": 800,
    "finnhub": 86400,
    "alphavantage": 25
}

STATE_FILE = Path.home() / "bot-a" / "logs" / ".api_state.json"


def load_state():
    """Load API usage state"""
    if not STATE_FILE.exists():
        return {"date": str(datetime.now().date()), "calls": {}}
    
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    
    # Reset if new day
    if state.get("date") != str(datetime.now().date()):
        state = {"date": str(datetime.now().date()), "calls": {}}
    
    return state


def save_state(state):
    """Save API usage state"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def record_call(provider="twelvedata"):
    """Record an API call"""
    state = load_state()
    state["calls"][provider] = state["calls"].get(provider, 0) + 1
    save_state(state)
    return state["calls"][provider]


def check_quota(provider="twelvedata"):
    """Check if we're within quota"""
    state = load_state()
    calls = state["calls"].get(provider, 0)
    limit = LIMITS.get(provider, 800)
    
    remaining = limit - calls
    percent_used = (calls / limit) * 100
    
    return {
        "provider": provider,
        "calls_today": calls,
        "limit": limit,
        "remaining": remaining,
        "percent_used": round(percent_used, 1),
        "ok": calls < (limit * 0.9)
    }


def get_status():
    """Get full API status"""
    state = load_state()
    status = []
    
    for provider, limit in LIMITS.items():
        calls = state["calls"].get(provider, 0)
        status.append({
            "provider": provider,
            "calls": calls,
            "limit": limit,
            "remaining": limit - calls,
            "percent": round((calls/limit)*100, 1)
        })
    
    return status


if __name__ == "__main__":
    print("=== API Circuit Breaker Status ===\n")
    
    status = get_status()
    for s in status:
        emoji = "🟢" if s["percent"] < 50 else "🟡" if s["percent"] < 90 else "🔴"
        print(f"{emoji} {s['provider'].upper()}")
        print(f"   Calls: {s['calls']}/{s['limit']} ({s['percent']}%)")
        print(f"   Remaining: {s['remaining']}\n")
    
    check = check_quota("twelvedata")
    if check["ok"]:
        print(f"✅ TwelveData: {check['remaining']} calls remaining today")
    else:
        print(f"⚠️  TwelveData: Approaching limit ({check['percent_used']}%)")
