#!/usr/bin/env python3
"""
Adaptive Frequency Manager for BotA
Switches timeframes based on volatility and market conditions
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from api_circuit_breaker import check_quota, record_call

# Volatility thresholds (ATR-based)
THRESHOLDS = {
    "low": 0.0015,      # < 15 pips/hour
    "medium": 0.0030,   # 15-30 pips/hour
    "high": 0.0050,     # > 30 pips/hour
    "extreme": 0.0100   # > 100 pips/hour (news events)
}

# Timeframe recommendations
TF_STRATEGY = {
    "low": {"tf": "H1", "calls_per_day": 24, "description": "Normal hourly"},
    "medium": {"tf": "M15", "calls_per_day": 96, "description": "Increased monitoring"},
    "high": {"tf": "M5", "calls_per_day": 288, "description": "Active trading"},
    "extreme": {"tf": "M1", "calls_per_day": 720, "description": "News event mode"}
}

STATE_FILE = Path.home() / "bot-a" / "logs" / ".frequency_state.json"


def calculate_volatility(pair="EURUSD", bars=24):
    """Calculate current volatility using recent data"""
    from data.ohlcv import fetch
    
    try:
        # Fetch recent H1 data
        rows = fetch(pair, "H1", bars)
        
        if not rows or len(rows) < 2:
            return None
        
        # Calculate ATR (simple version: average of high-low)
        ranges = [(r["high"] - r["low"]) for r in rows if "high" in r and "low" in r]
        
        if not ranges:
            return None
        
        atr = sum(ranges) / len(ranges)
        return atr
        
    except Exception as e:
        print(f"Error calculating volatility: {e}")
        return None


def check_news_events():
    """Check for upcoming high-impact news events"""
    # Placeholder - would integrate with news API
    # For now, check if it's major news times (London open, NY open, etc.)
    now = datetime.utcnow()
    hour = now.hour
    
    # High volatility times (UTC)
    high_impact_hours = [
        (7, 9),   # London open
        (12, 14), # NY open
        (13, 14), # NY+London overlap
    ]
    
    for start, end in high_impact_hours:
        if start <= hour < end:
            return "medium"  # Increased attention during key hours
    
    return "low"


def get_recommended_frequency():
    """Get recommended timeframe based on market conditions"""
    
    # Check API quota first
    quota = check_quota("twelvedata")
    if not quota["ok"]:
        print(f"⚠️  API quota low ({quota['percent_used']}%), staying on H1")
        return TF_STRATEGY["low"]
    
    # Calculate volatility
    volatility = calculate_volatility()
    
    if volatility is None:
        print("⚠️  Could not calculate volatility, defaulting to H1")
        return TF_STRATEGY["low"]
    
    # Determine volatility level
    if volatility > THRESHOLDS["extreme"]:
        level = "extreme"
        emoji = "🔥"
    elif volatility > THRESHOLDS["high"]:
        level = "high"
        emoji = "⚡"
    elif volatility > THRESHOLDS["medium"]:
        level = "medium"
        emoji = "📈"
    else:
        level = "low"
        emoji = "💤"
    
    # Check for news events
    news_level = check_news_events()
    if news_level == "medium" and level == "low":
        level = "medium"
        emoji = "📰"
    
    strategy = TF_STRATEGY[level]
    
    # Safety check: don't exceed 90% of daily quota
    remaining = quota["remaining"]
    if strategy["calls_per_day"] > (remaining * 1.1):
        print(f"⚠️  {strategy['tf']} would exceed quota, throttling...")
        return TF_STRATEGY["low"]
    
    print(f"{emoji} Volatility: {volatility:.5f} ({level})")
    print(f"📊 Recommended: {strategy['tf']} ({strategy['description']})")
    print(f"📞 API Impact: {strategy['calls_per_day']}/800 daily calls")
    
    return strategy


def save_frequency_state(strategy):
    """Save current frequency strategy"""
    state = {
        "timestamp": datetime.utcnow().isoformat(),
        "timeframe": strategy["tf"],
        "calls_per_day": strategy["calls_per_day"],
        "description": strategy["description"]
    }
    
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_frequency_state():
    """Load last frequency strategy"""
    if not STATE_FILE.exists():
        return TF_STRATEGY["low"]
    
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        
        # Find matching strategy
        for level, strategy in TF_STRATEGY.items():
            if strategy["tf"] == state.get("timeframe"):
                return strategy
        
        return TF_STRATEGY["low"]
    except:
        return TF_STRATEGY["low"]


if __name__ == "__main__":
    print("=== BotA Adaptive Frequency Manager ===\n")
    
    # Show current state
    current = load_frequency_state()
    print(f"Current Mode: {current['tf']} ({current['description']})")
    print()
    
    # Get recommendation
    recommended = get_recommended_frequency()
    
    # Save if different
    if recommended["tf"] != current["tf"]:
        save_frequency_state(recommended)
        print(f"\n✅ Switching from {current['tf']} to {recommended['tf']}")
    else:
        print(f"\n✅ Staying on {current['tf']}")
    
    print(f"\n📊 Volatility Thresholds:")
    print(f"   Low:     < {THRESHOLDS['low']:.4f} (H1 - 24 calls/day)")
    print(f"   Medium:  < {THRESHOLDS['medium']:.4f} (M15 - 96 calls/day)")
    print(f"   High:    < {THRESHOLDS['high']:.4f} (M5 - 288 calls/day)")
    print(f"   Extreme: > {THRESHOLDS['high']:.4f} (M1 - burst mode)")
