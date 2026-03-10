#!/usr/bin/env python3
"""
News Event Monitor for BotA
Detects high-impact news and triggers frequency increase
"""

from datetime import datetime, time, timezone

# High-impact news schedule (UTC times)
SCHEDULED_EVENTS = {
    "NFP": {  # Non-Farm Payrolls (First Friday of month)
        "time": time(12, 30),
        "duration_hours": 2,
        "impact": "extreme"
    },
    "FOMC": {  # Fed meetings (8 times per year)
        "time": time(18, 0),
        "duration_hours": 3,
        "impact": "extreme"
    },
    "ECB": {  # ECB meetings
        "time": time(11, 45),
        "duration_hours": 2,
        "impact": "high"
    },
    "CPI": {  # Inflation data (monthly)
        "time": time(12, 30),
        "duration_hours": 1,
        "impact": "high"
    }
}

# Session times (UTC)
TRADING_SESSIONS = {
    "tokyo": {"open": time(0, 0), "close": time(9, 0), "volatility": "low"},
    "london": {"open": time(7, 0), "close": time(16, 0), "volatility": "high"},
    "ny": {"open": time(12, 0), "close": time(21, 0), "volatility": "high"},
    "overlap": {"open": time(12, 0), "close": time(16, 0), "volatility": "extreme"}
}


def get_current_session():
    """Detect which trading session is active"""
    now = datetime.now(timezone.utc).time()
    
    for session, times in TRADING_SESSIONS.items():
        if times["open"] <= now < times["close"]:
            return session, times["volatility"]
    
    return "after_hours", "low"


def should_increase_frequency():
    """Determine if we should increase monitoring frequency"""
    session, vol_level = get_current_session()
    now = datetime.now(timezone.utc)
    
    # Check if major session overlap
    if session == "overlap":
        return True, "NY-London overlap (highest volume)"
    
    # Check if London or NY session
    if session in ["london", "ny"]:
        return True, f"{session.capitalize()} session active"
    
    # Check if close to round hour (often has moves)
    if now.minute < 5:
        return True, "Top of hour (potential volatility)"
    
    return False, "Low activity period"


if __name__ == "__main__":
    print("=== News & Session Monitor ===\n")
    
    session, vol = get_current_session()
    should_increase, reason = should_increase_frequency()
    
    now = datetime.now(timezone.utc)
    print(f"🕒 Current Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"📍 Session: {session.upper()} ({vol} volatility)")
    print(f"📊 Recommendation: {'INCREASE' if should_increase else 'NORMAL'} frequency")
    print(f"💡 Reason: {reason}")
    
    print(f"\n📅 Trading Sessions (UTC):")
    for name, times in TRADING_SESSIONS.items():
        print(f"   {name.capitalize()}: {times['open']} - {times['close']}")
