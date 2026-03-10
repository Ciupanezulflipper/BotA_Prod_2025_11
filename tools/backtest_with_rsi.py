#!/usr/bin/env python3
"""Backtest WITH RSI filter to see improvement"""

import pandas as pd
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / 'bot-a' / 'tools'))

from dotenv import load_dotenv
import os

env_file = Path.home() / 'bot-a' / '.env.botA'
load_dotenv(env_file)

api_key = os.getenv('TWELVEDATA_API_KEY')

from atr_sltp_conservative import calculate_atr, calculate_sltp_atr

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

print("🔍 Fetching data with RSI filter test...")

url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1h&outputsize=100&apikey={api_key}"

response = requests.get(url, timeout=10)
data = response.json()

rows = data['values']
df = pd.DataFrame(rows)
df.columns = [c.lower() for c in df.columns]
df = df.rename(columns={'high':'h', 'low':'l', 'close':'c', 'open':'o'})
df = df.astype({'h':float, 'l':float, 'c':float, 'o':float})
df = df.iloc[::-1].reset_index(drop=True)

print(f"✅ Loaded {len(df)} candles\n")

trades_no_rsi = []
trades_with_rsi = []

for i in range(20, len(df)):
    subset = df.iloc[i-20:i+1]
    
    sma20 = subset['c'].rolling(20).mean().iloc[-1]
    rsi = calculate_rsi(subset['c']).iloc[-1]
    price = subset['c'].iloc[-1]
    pct_diff = (price - sma20) / sma20
    
    if pct_diff > 0.0015:
        action = "BUY"
    elif price < sma20:
        action = "SELL"
    else:
        continue
    
    # Test WITHOUT RSI
    atr = calculate_atr(subset)
    sl, tp, rr, sl_pips, tp_pips = calculate_sltp_atr(price, action, atr)
    
    hit_tp = False
    hit_sl = False
    
    for j in range(i+1, min(i+11, len(df))):
        high = df['h'].iloc[j]
        low = df['l'].iloc[j]
        
        if action == "BUY":
            if high >= tp:
                hit_tp = True
                break
            elif low <= sl:
                hit_sl = True
                break
        else:
            if low <= tp:
                hit_tp = True
                break
            elif high >= sl:
                hit_sl = True
                break
    
    result = "WIN" if hit_tp else ("LOSS" if hit_sl else "PENDING")
    trades_no_rsi.append(result)
    
    # Test WITH RSI filter
    rsi_ok = True
    if action == "BUY" and rsi > 70:
        rsi_ok = False  # Overbought, skip
    elif action == "SELL" and rsi < 30:
        rsi_ok = False  # Oversold, skip
    
    if rsi_ok:
        trades_with_rsi.append(result)

wins_no = sum(1 for t in trades_no_rsi if t == 'WIN')
loss_no = sum(1 for t in trades_no_rsi if t == 'LOSS')

wins_yes = sum(1 for t in trades_with_rsi if t == 'WIN')
loss_yes = sum(1 for t in trades_with_rsi if t == 'LOSS')

print("="*60)
print("📊 COMPARISON: WITHOUT vs WITH RSI Filter")
print("="*60)

print("\n❌ WITHOUT RSI Filter:")
print(f"   Total Trades: {len(trades_no_rsi)}")
print(f"   Wins: {wins_no}, Losses: {loss_no}")
if wins_no + loss_no > 0:
    wr_no = wins_no / (wins_no + loss_no) * 100
    print(f"   Win Rate: {wr_no:.1f}%")

print("\n✅ WITH RSI Filter:")
print(f"   Total Trades: {len(trades_with_rsi)}")
print(f"   Wins: {wins_yes}, Losses: {loss_yes}")
if wins_yes + loss_yes > 0:
    wr_yes = wins_yes / (wins_yes + loss_yes) * 100
    print(f"   Win Rate: {wr_yes:.1f}%")
    
    if wr_yes > wr_no:
        improvement = wr_yes - wr_no
        print(f"\n🎯 IMPROVEMENT: +{improvement:.1f}% win rate!")
        print("   ✅ RSI filter HELPS!")
    else:
        print("\n   RSI didn't help this period")

print("="*60)
