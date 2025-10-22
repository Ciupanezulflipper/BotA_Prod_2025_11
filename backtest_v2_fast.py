#!/usr/bin/env python3
"""
Fast backtest - Test V1 vs V2 on available data
Goal: Get PF, WR, DD within 10 minutes
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Load data
data_file = Path.home() / "bot-a" / "data" / "EURUSD_H1.csv"

if not data_file.exists():
    print("❌ Data file not found. Run Phase 2 first!")
    sys.exit(1)

print("📊 Loading data...")
df = pd.read_csv(data_file)

# Ensure correct columns
if 'close' not in df.columns and 'c' in df.columns:
    df['close'] = df['c']
if 'high' not in df.columns and 'h' in df.columns:
    df['high'] = df['h']
if 'low' not in df.columns and 'l' in df.columns:
    df['low'] = df['l']

print(f"✅ Loaded {len(df)} bars")
print(f"📅 Range: {df['datetime'].iloc[0] if 'datetime' in df.columns else 'N/A'}")

# Calculate indicators
print("\n📈 Calculating indicators...")

# SMA20
df['sma20'] = df['close'].rolling(20).mean()

# ATR14
df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['atr14'] = df['tr'].rolling(14).mean()

# ADX (simplified)
df['atr_pct'] = (df['atr14'] / df['close']) * 100

# Volatility
df['volatility'] = (df['close'].rolling(20).std() / df['close'].rolling(20).mean()) * 100

# Strategy V1: SMA20 Crossover
print("\n🧪 Testing V1 (SMA20 Crossover)...")

trades_v1 = []
in_trade = False
entry_price = 0
entry_type = None

for i in range(50, len(df)):  # Start after indicators warm up
    row = df.iloc[i]
    
    # Skip if volatility too low
    if row['volatility'] < 0.2:
        continue
    
    # Entry logic
    if not in_trade:
        pct_above_sma = ((row['close'] - row['sma20']) / row['sma20']) * 100
        
        if pct_above_sma > 0.15:  # BUY signal
            entry_price = row['close']
            entry_type = 'BUY'
            in_trade = True
            
            # Calculate SL/TP
            sl = entry_price - (row['atr14'] * 1.5)
            tp = entry_price + (row['atr14'] * 2.5)
            
        elif pct_above_sma < -0.15:  # SELL signal
            entry_price = row['close']
            entry_type = 'SELL'
            in_trade = True
            
            sl = entry_price + (row['atr14'] * 1.5)
            tp = entry_price - (row['atr14'] * 2.5)
    
    # Exit logic
    if in_trade:
        if entry_type == 'BUY':
            if row['low'] <= sl:
                result = 'LOSS'
                pnl = sl - entry_price
                in_trade = False
                trades_v1.append({'type': entry_type, 'result': result, 'pnl': pnl})
            elif row['high'] >= tp:
                result = 'WIN'
                pnl = tp - entry_price
                in_trade = False
                trades_v1.append({'type': entry_type, 'result': result, 'pnl': pnl})
        
        elif entry_type == 'SELL':
            if row['high'] >= sl:
                result = 'LOSS'
                pnl = entry_price - sl
                in_trade = False
                trades_v1.append({'type': entry_type, 'result': result, 'pnl': pnl})
            elif row['low'] <= tp:
                result = 'WIN'
                pnl = entry_price - tp
                in_trade = False
                trades_v1.append({'type': entry_type, 'result': result, 'pnl': pnl})

# Calculate V1 metrics
if trades_v1:
    trades_df = pd.DataFrame(trades_v1)
    wins = len(trades_df[trades_df['result'] == 'WIN'])
    losses = len(trades_df[trades_df['result'] == 'LOSS'])
    total_trades = len(trades_df)
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    print(f"\n📊 V1 RESULTS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate:.1f}%)")
    print(f"   Losses: {losses}")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Net P&L: {trades_df['pnl'].sum():.4f}")
    
    # Quick verdict
    if profit_factor >= 1.3 and win_rate >= 50:
        print(f"   ✅ VIABLE (PF≥1.3, WR≥50%)")
    elif profit_factor >= 1.2 and win_rate >= 45:
        print(f"   ⚠️ MARGINAL (needs improvement)")
    else:
        print(f"   ❌ NOT VIABLE (needs major changes)")
else:
    print("❌ No trades generated!")

print("\n" + "="*60)
print("✅ Quick backtest complete!")
print("Next: Run full walk-forward if results promising")
