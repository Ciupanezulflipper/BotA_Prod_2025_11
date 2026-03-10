#!/usr/bin/env python3
"""Quick backtest with proper env loading"""

import pandas as pd
import requests
import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path.home() / 'bot-a' / 'tools'))

# Load env the same way runner does
from dotenv import load_dotenv
import os

env_file = Path.home() / 'bot-a' / '.env.botA'
load_dotenv(env_file)

# Try multiple key names (in case of alias)
api_key = (
    os.getenv('TWELVEDATA_API_KEY') or 
    os.getenv('TD_API_KEY') or
    os.getenv('API_KEY_TWELVEDATA')
)

if not api_key:
    print("❌ No API key found!")
    print("Checking .env.botA...")
    with open(env_file) as f:
        for line in f:
            if 'TWELVE' in line.upper() or 'TD_API' in line.upper():
                print(f"  Found: {line.strip()[:50]}...")
    exit(1)

print(f"✅ Using API key: {api_key[:10]}...")

from atr_sltp_conservative import calculate_atr, calculate_sltp_atr

print("🔍 Fetching 100 hours of EURUSD data...")

url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1h&outputsize=100&apikey={api_key}"

response = requests.get(url, timeout=10)
data = response.json()

if 'values' not in data:
    print(f"❌ API Error: {data}")
    exit(1)

rows = data['values']
df = pd.DataFrame(rows)
df.columns = [c.lower() for c in df.columns]
df = df.rename(columns={'high':'h', 'low':'l', 'close':'c', 'open':'o'})
df = df.astype({'h':float, 'l':float, 'c':float, 'o':float})
df = df.iloc[::-1].reset_index(drop=True)

print(f"✅ Loaded {len(df)} candles\n")

trades = []
for i in range(20, len(df)):
    subset = df.iloc[i-20:i+1]
    
    sma20 = subset['c'].rolling(20).mean().iloc[-1]
    price = subset['c'].iloc[-1]
    pct_diff = (price - sma20) / sma20
    
    if pct_diff > 0.0015:
        action = "BUY"
    elif price < sma20:
        action = "SELL"
    else:
        continue
    
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
    trades.append({
        'action': action,
        'entry': price,
        'sl_pips': sl_pips,
        'tp_pips': tp_pips,
        'result': result
    })

wins = sum(1 for t in trades if t['result'] == 'WIN')
losses = sum(1 for t in trades if t['result'] == 'LOSS')
pending = sum(1 for t in trades if t['result'] == 'PENDING')

print("="*60)
print("🎯 BACKTEST RESULTS (Last 100 Hours)")
print("="*60)
print(f"Total Signals: {len(trades)}")
print(f"✅ Wins: {wins}")
print(f"❌ Losses: {losses}")
print(f"⏳ Pending: {pending}")

if wins + losses > 0:
    win_rate = wins / (wins + losses) * 100
    print(f"\n📊 Win Rate: {win_rate:.1f}%")
    
    avg_win = sum(t['tp_pips'] for t in trades if t['result'] == 'WIN') / max(wins, 1)
    avg_loss = sum(t['sl_pips'] for t in trades if t['result'] == 'LOSS') / max(losses, 1)
    
    print(f"📈 Avg Win: {avg_win:.1f} pips")
    print(f"📉 Avg Loss: {avg_loss:.1f} pips")
    
    if wins > 0 and losses > 0:
        profit_factor = (wins * avg_win) / (losses * avg_loss)
        print(f"💰 Profit Factor: {profit_factor:.2f}")
    
    print("\n" + "="*60)
    if win_rate >= 60:
        print("✅ EXCELLENT! Ready for multi-pair!")
    elif win_rate >= 50:
        print("✅ GOOD! Add RSI to boost to 60%+")
    else:
        print("⚠️ MUST add RSI filter first!")
else:
    print("\n⚠️ Not enough completed trades")

print("\nLast 10 Trades:")
for t in trades[-10:]:
    emoji = "✅" if t['result'] == "WIN" else "❌" if t['result'] == "LOSS" else "⏳"
    print(f"  {emoji} {t['action']:4} @ {t['entry']:.5f} → {t['result']:7}")
