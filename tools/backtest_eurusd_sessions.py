#!/usr/bin/env python3
"""
Re-test EURUSD with London/NY session filter
See if frequency improves with higher quality signals
"""

import pandas as pd
import numpy as np
from pathlib import Path

data_file = Path.home() / "bot-a" / "data" / "EURUSD_H1_5000.csv"

print("📊 EURUSD BACKTEST - WITH SESSION FILTER")
print("="*60)
print("")

df = pd.read_csv(data_file)

for col in ['open', 'high', 'low', 'close']:
    if col not in df.columns:
        df[col] = df[col[0]]

# Parse datetime and add session filter
df['datetime'] = pd.to_datetime(df['datetime'])
df['hour'] = df['datetime'].dt.hour

# London/NY overlap: 13:00-17:00 UTC
df['in_session'] = (df['hour'] >= 13) & (df['hour'] < 17)

print(f"✅ Loaded {len(df)} bars")
print(f"📅 In session: {df['in_session'].sum()} bars ({df['in_session'].sum()/len(df)*100:.1f}%)")
print("")

# Calculate indicators
df['sma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2.0)
df['bb_lower'] = df['sma20'] - (df['std20'] * 2.0)
df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['atr14'] = df['tr'].rolling(14).mean()
df['volatility'] = (df['close'].rolling(20).std() / df['close'].rolling(20).mean()) * 100

delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['rsi14'] = 100 - (100 / (1 + rs))

high = df['high']
low = df['low']
close = df['close']

tr_adx = pd.concat([
    high - low,
    abs(high - close.shift(1)),
    abs(low - close.shift(1))
], axis=1).max(axis=1)

atr_adx = tr_adx.rolling(14).mean()
up_move = high.diff()
down_move = -low.diff()

plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move

plus_di = 100 * (plus_dm.rolling(14).mean() / atr_adx)
minus_di = 100 * (minus_dm.rolling(14).mean() / atr_adx)

dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
df['adx'] = dx.rolling(14).mean()

# Run strategy - count signals both ways
print("🧪 Analyzing signal distribution...")
print("")

trades_all = []
trades_session = []

for i in range(100, len(df)):
    row = df.iloc[i]
    
    if pd.isna(row['bb_position']) or pd.isna(row['rsi14']) or pd.isna(row['adx']):
        continue
    
    if row['volatility'] < 0.25:
        continue
    
    if row['adx'] > 25:
        continue
    
    # Check if signal would generate
    signal = None
    if row['bb_position'] < 0.2 and row['rsi14'] < 40:
        signal = 'BUY'
    elif row['bb_position'] > 0.8 and row['rsi14'] > 60:
        signal = 'SELL'
    
    if signal:
        trades_all.append({'signal': signal, 'in_session': row['in_session'], 'hour': row['hour']})
        
        if row['in_session']:
            trades_session.append({'signal': signal, 'hour': row['hour']})

# Results
print("="*60)
print("📊 SESSION FILTER IMPACT ANALYSIS")
print("="*60)
print("")

print(f"24/7 TRADING (current approach):")
print(f"  Total signals: {len(trades_all)}")
print(f"  Signals per month: {len(trades_all)/10:.1f}")
print("")

print(f"LONDON/NY ONLY (13:00-17:00 UTC):")
print(f"  Total signals: {len(trades_session)}")
print(f"  Signals per month: {len(trades_session)/10:.1f}")
print("")

if len(trades_all) > 0:
    reduction = (1 - len(trades_session)/len(trades_all)) * 100
    kept = len(trades_session) / len(trades_all) * 100
    
    print(f"📉 IMPACT:")
    print(f"  Signals kept: {kept:.0f}%")
    print(f"  Signals filtered: {reduction:.0f}%")
    print("")
    
    # Show hour distribution
    df_all = pd.DataFrame(trades_all)
    print("📈 SIGNAL DISTRIBUTION BY HOUR (UTC):")
    hour_dist = df_all['hour'].value_counts().sort_index()
    for hour, count in hour_dist.items():
        in_window = "✅" if 13 <= hour < 17 else "❌"
        adelaide_hour = (hour + 10) % 24  # Rough conversion
        print(f"  {hour:02d}:00 UTC ({adelaide_hour:02d}:00 Adelaide): {count} signals {in_window}")
    print("")
    
    print("🎯 DEEPSEEK'S THEORY:")
    print("  'Session filtering could 3X your win rate'")
    print("")
    
    print("💡 REALITY CHECK:")
    if len(trades_session) == 0:
        print("  ❌ NO signals during London/NY!")
        print("  ⚠️ Session filter would KILL the strategy")
    elif len(trades_session) >= len(trades_all) * 0.5:
        print(f"  ✅ {kept:.0f}% of signals in prime hours")
        print("  ✅ Quality improvement likely")
        print(f"  ✅ Still get {len(trades_session)/10:.1f} trades/month")
    else:
        print(f"  ⚠️ Only {kept:.0f}% of signals in window")
        print("  ⚠️ Frequency drops significantly")
    
    print("")
    print("⏰ ADELAIDE TIME REALITY:")
    print("  London/NY = 13:00-17:00 UTC")
    print("  Adelaide = 23:30-03:30 (late night!)")
    print("  ⚠️ Can you execute trades at midnight-3am?")
else:
    print("❌ No signals found in dataset!")

print("")
print("="*60)
