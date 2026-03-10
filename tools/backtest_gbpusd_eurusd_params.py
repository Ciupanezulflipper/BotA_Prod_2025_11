#!/usr/bin/env python3
"""
GBPUSD with EURUSD's EXACT parameters
(not Grok's optimizations)
"""

import pandas as pd
import numpy as np
from pathlib import Path

data_file = Path.home() / "bot-a" / "data" / "GBPUSD_H1_5000.csv"

print("📊 GBPUSD with EURUSD PARAMETERS")
print("="*60)
print("")

df = pd.read_csv(data_file)

for col in ['open', 'high', 'low', 'close']:
    if col not in df.columns:
        df[col] = df[col[0]]

print(f"✅ Loaded {len(df)} bars")
print("")

# EURUSD parameters (not optimized)
print("📈 Using EURUSD's exact parameters:")
print("   • BB: 2.0 SD (standard)")
print("   • RSI: <40/>60 (original)")
print("   • ADX: <25 (original)")
print("   • Vol: >0.25%")
print("")

# Calculate indicators - EURUSD settings
df['sma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2.0)  # Standard
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

# Run EURUSD strategy
trades = []
in_trade = False
entry_price = 0
entry_type = None
sl = 0
tp = 0

for i in range(100, len(df)):
    row = df.iloc[i]
    
    if pd.isna(row['bb_position']) or pd.isna(row['rsi14']) or pd.isna(row['adx']):
        continue
    
    if row['volatility'] < 0.25:
        continue
    
    if row['adx'] > 25:  # Original threshold
        continue
    
    if not in_trade:
        # EURUSD thresholds
        if row['bb_position'] < 0.2 and row['rsi14'] < 40:
            entry_price = row['close']
            entry_type = 'BUY'
            in_trade = True
            sl = entry_price - (row['atr14'] * 1.5)
            tp = row['sma20']
            
        elif row['bb_position'] > 0.8 and row['rsi14'] > 60:
            entry_price = row['close']
            entry_type = 'SELL'
            in_trade = True
            sl = entry_price + (row['atr14'] * 1.5)
            tp = row['sma20']
    
    if in_trade:
        if entry_type == 'BUY':
            if row['low'] <= sl:
                pnl = sl - entry_price
                trades.append({'type': 'BUY', 'result': 'LOSS', 'pnl': pnl})
                in_trade = False
            elif row['close'] >= tp:
                pnl = tp - entry_price
                trades.append({'type': 'BUY', 'result': 'WIN', 'pnl': pnl})
                in_trade = False
        
        elif entry_type == 'SELL':
            if row['high'] >= sl:
                pnl = entry_price - sl
                trades.append({'type': 'SELL', 'result': 'LOSS', 'pnl': pnl})
                in_trade = False
            elif row['close'] <= tp:
                pnl = entry_price - tp
                trades.append({'type': 'SELL', 'result': 'WIN', 'pnl': pnl})
                in_trade = False

print("="*60)
print("📊 RESULTS (EURUSD PARAMS ON GBPUSD)")
print("="*60)
print("")

if len(trades) > 0:
    trades_df = pd.DataFrame(trades)
    
    total = len(trades_df)
    wins = len(trades_df[trades_df['result'] == 'WIN'])
    losses = total - wins
    wr = (wins / total * 100)
    
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    net_pnl = trades_df['pnl'].sum()
    
    print(f"Total Trades: {total}")
    print(f"Wins: {wins} ({wr:.1f}%)")
    print(f"Losses: {losses}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Net P&L: {net_pnl:.4f} ({net_pnl*10000:.1f} pips)")
    print(f"Trades/Month: {total/10:.1f}")
    print("")
    
    print("📈 COMPARISON:")
    print(f"   EURUSD: 7 trades, 57% WR, 2.58 PF")
    print(f"   GBPUSD: {total} trades, {wr:.1f}% WR, {pf:.2f} PF")
    print("")
    
    print("🎯 VERDICT:")
    if pf >= 2.0 and wr >= 50:
        print("   ✅ WORKS! GBPUSD viable with EURUSD params")
    elif pf >= 1.5:
        print("   ⚠️ MARGINAL - Weaker than EURUSD")
    else:
        print("   ❌ FAILED - Stick with EURUSD only")
else:
    print("❌ No trades!")

print("")
print("="*60)
