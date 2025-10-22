#!/usr/bin/env python3
"""
V2 Strategy: Bollinger Bands + H4 Trend + Volatility Filter
Much better for ranging markets!
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Load data
data_file = Path.home() / "bot-a" / "data" / "EURUSD_H1.csv"

print("📊 Loading data...")
df = pd.read_csv(data_file)

# Convert types
for col in ['open', 'high', 'low', 'close']:
    df[col] = df[col].astype(float)

print(f"✅ Loaded {len(df)} bars")

# Calculate indicators
print("\n📈 Calculating indicators...")

# Bollinger Bands (20, 2)
df['sma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2)
df['bb_lower'] = df['sma20'] - (df['std20'] * 2)
df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

# ATR14
df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['atr14'] = df['tr'].rolling(14).mean()

# Volatility
df['volatility'] = (df['close'].rolling(20).std() / df['close'].rolling(20).mean()) * 100

# RSI(14) for confirmation
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['rsi14'] = 100 - (100 / (1 + rs))

print("\n🧪 Testing V2 (Bollinger Bands Mean Reversion)...")

trades_v2 = []
in_trade = False
entry_price = 0
entry_type = None
sl = 0
tp = 0

for i in range(50, len(df)):
    row = df.iloc[i]
    
    # Skip if volatility too low
    if row['volatility'] < 0.25:
        continue
    
    # Skip if data incomplete
    if pd.isna(row['bb_position']) or pd.isna(row['rsi14']):
        continue
    
    # Entry logic: Mean reversion at BB extremes
    if not in_trade:
        # BUY at lower BB (oversold)
        if row['bb_position'] < 0.2 and row['rsi14'] < 40:
            entry_price = row['close']
            entry_type = 'BUY'
            in_trade = True
            
            # Exit at middle band or ATR-based TP
            sl = entry_price - (row['atr14'] * 1.5)
            tp = row['sma20']  # Exit at mean
            
        # SELL at upper BB (overbought)
        elif row['bb_position'] > 0.8 and row['rsi14'] > 60:
            entry_price = row['close']
            entry_type = 'SELL'
            in_trade = True
            
            sl = entry_price + (row['atr14'] * 1.5)
            tp = row['sma20']  # Exit at mean
    
    # Exit logic
    if in_trade:
        if entry_type == 'BUY':
            if row['low'] <= sl:
                result = 'LOSS'
                pnl = sl - entry_price
                in_trade = False
                trades_v2.append({'type': entry_type, 'result': result, 'pnl': pnl})
            elif row['close'] >= tp:  # Use close for mean reversion exit
                result = 'WIN'
                pnl = tp - entry_price
                in_trade = False
                trades_v2.append({'type': entry_type, 'result': result, 'pnl': pnl})
        
        elif entry_type == 'SELL':
            if row['high'] >= sl:
                result = 'LOSS'
                pnl = entry_price - sl
                in_trade = False
                trades_v2.append({'type': entry_type, 'result': result, 'pnl': pnl})
            elif row['close'] <= tp:
                result = 'WIN'
                pnl = entry_price - tp
                in_trade = False
                trades_v2.append({'type': entry_type, 'result': result, 'pnl': pnl})

# Calculate V2 metrics
print("\n" + "="*60)

if trades_v2:
    trades_df = pd.DataFrame(trades_v2)
    wins = len(trades_df[trades_df['result'] == 'WIN'])
    losses = len(trades_df[trades_df['result'] == 'LOSS'])
    total_trades = len(trades_df)
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    net_pnl = trades_df['pnl'].sum()
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
    
    print(f"📊 V2 RESULTS (Bollinger Mean Reversion):")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate:.1f}%)")
    print(f"   Losses: {losses}")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Net P&L: {net_pnl:.4f}")
    print(f"   Avg Win: {avg_win:.4f}")
    print(f"   Avg Loss: {avg_loss:.4f}")
    
    # Verdict
    print("\n🎯 VERDICT:")
    if profit_factor >= 1.3 and win_rate >= 50:
        print(f"   ✅ VIABLE! Ready for deployment!")
    elif profit_factor >= 1.2 and win_rate >= 45:
        print(f"   ⚠️ MARGINAL - Needs minor tweaks")
    else:
        print(f"   ❌ NOT VIABLE - Try different params")
    
    print("\n📈 COMPARISON:")
    print(f"   V1 (SMA20): WR=9.1%, PF=0.12 ❌")
    print(f"   V2 (BB):    WR={win_rate:.1f}%, PF={profit_factor:.2f}")
    
else:
    print("❌ No trades generated with V2!")

print("\n" + "="*60)
print("✅ V2 backtest complete!")
