#!/usr/bin/env python3
"""
Strategy V2: Hybrid (Trend + Mean Reversion)
- H4 trend filter (only trade WITH the trend)
- Bollinger Bands for entry (buy dips, sell rallies)
- Volatility guard (skip if < 0.3%)
"""

import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

env_file = Path.home() / 'bot-a' / '.env.botA'
load_dotenv(env_file)

api_key = os.getenv('TWELVEDATA_API_KEY')

def get_h4_trend(pair="EUR/USD"):
    """Get H4 trend direction"""
    url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval=4h&outputsize=50&apikey={api_key}"
    
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if 'values' not in data:
        return None
    
    rows = data['values']
    df = pd.DataFrame(rows)
    df['close'] = df['close'].astype(float)
    df = df.iloc[::-1]
    
    sma20 = df['close'].rolling(20).mean().iloc[-1]
    price = df['close'].iloc[-1]
    
    if price > sma20 * 1.001:
        return "UPTREND"
    elif price < sma20 * 0.999:
        return "DOWNTREND"
    else:
        return "NEUTRAL"

def calculate_bollinger_bands(df, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = df['c'].rolling(period).mean()
    std = df['c'].rolling(period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper.iloc[-1], sma.iloc[-1], lower.iloc[-1]

def get_signal_v2(pair="EUR/USD", tf="1h"):
    """
    V2 Strategy with filters:
    1. H4 trend must be clear
    2. H1 entry near Bollinger Band
    3. Volatility > 0.3%
    """
    # Get H1 data
    url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval={tf}&outputsize=50&apikey={api_key}"
    
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if 'values' not in data:
        return None, None, "API Error"
    
    rows = data['values']
    df = pd.DataFrame(rows)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={'high':'h', 'low':'l', 'close':'c', 'open':'o'})
    df = df.astype({'h':float, 'l':float, 'c':float, 'o':float})
    df = df.iloc[::-1]
    
    # Check volatility
    volatility = (df['c'].std() / df['c'].mean()) * 100
    
    if volatility < 0.25:
        return "WAIT", 0, "Volatility too low (ranging market)"
    
    # Get H4 trend
    h4_trend = get_h4_trend(pair)
    
    if h4_trend == "NEUTRAL":
        return "WAIT", 0, "No clear H4 trend"
    
    # Calculate Bollinger Bands
    upper, middle, lower = calculate_bollinger_bands(df)
    price = df['c'].iloc[-1]
    
    # Mean reversion logic
    band_position = (price - lower) / (upper - lower)
    
    if h4_trend == "UPTREND":
        if band_position < 0.3:  # Near lower band
            return "BUY", 0.8, f"H4 up + dip to lower BB ({band_position:.2f})"
        elif band_position > 0.5:
            return "WAIT", 0, "Wait for dip in uptrend"
    
    elif h4_trend == "DOWNTREND":
        if band_position > 0.7:  # Near upper band
            return "SELL", 0.8, f"H4 down + rally to upper BB ({band_position:.2f})"
        elif band_position < 0.5:
            return "WAIT", 0, "Wait for rally in downtrend"
    
    return "WAIT", 0, "No setup"

if __name__ == "__main__":
    action, score, reason = get_signal_v2()
    
    print("="*60)
    print("🎯 STRATEGY V2 TEST")
    print("="*60)
    print(f"Action: {action}")
    print(f"Score: {score}")
    print(f"Reason: {reason}")
    print("="*60)
