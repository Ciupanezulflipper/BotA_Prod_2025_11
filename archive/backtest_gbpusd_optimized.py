#!/usr/bin/env python3
"""
GBPUSD Backtest with Grok's optimized parameters:
- BB: 2.5 SD (not 2.0)
- RSI: <25/>75 (not 30/70)
- ADX: <30 (not <25)
"""

import pandas as pd
import numpy as np
from pathlib import Path

data_file = Path.home() / "bot-a" / "data" / "GBPUSD_H1_5000.csv"

print("📊 GBPUSD BACKTEST (GROK OPTIMIZED PARAMS)")
print("="*60)
print("")

df = pd.read_csv(data_file)

# Column mapping
for col in ['open', 'high', 'low', 'close']:
    if col not in df.columns:
        df[col] = df[col[0]]

print(f"✅ Loaded {len(df)} bars")
print(f"📅 Range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
print("")

# Calculate indicators with OPTIMIZED parameters
print("📈 Calculating indicators (optimized for GBPUSD)...")

# Bollinger Bands - 2.5 SD (Grok recommendation)
df['sma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2.5)  # ← 2.5 not 2.0
df['bb_lower'] = df['sma20'] - (df['std20'] * 2.5)
df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

# ATR
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

# RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['rsi14'] = 100 - (100 / (1 + rs))

# ADX
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

print("✅ Indicators ready")
print("")

# Run optimized strategy
print("🧪 Running OPTIMIZED V2 for GBPUSD...")
print("   Parameters:")
print("   • BB: 2.5 SD (wider for GBP volatility)")
print("   • RSI: <25 oversold, >75 overbought (stricter)")
print("   • ADX: <30 for ranging (higher threshold)")
print("   • Vol: >0.25% minimum")
print("")

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
    
    # Volatility filter
    if row['volatility'] < 0.25:
        continue
    
    # ADX filter - OPTIMIZED: <30 not <25
    if row['adx'] > 30:
        continue
    
    # Entry logic - OPTIMIZED RSI thresholds
    if not in_trade:
        # BUY: More extreme oversold
        if row['bb_position'] < 0.2 and row['rsi14'] < 25:  # ← 25 not 40
            entry_price = row['close']
            entry_type = 'BUY'
            in_trade = True
            sl = entry_price - (row['atr14'] * 1.5)
            tp = row['sma20']
            
        # SELL: More extreme overbought
        elif row['bb_position'] > 0.8 and row['rsi14'] > 75:  # ← 75 not 60
            entry_price = row['close']
            entry_type = 'SELL'
            in_trade = True
            sl = entry_price + (row['atr14'] * 1.5)
            tp = row['sma20']
    
    # Exit logic
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

# Results
print("="*60)
print("📊 GBPUSD BACKTEST RESULTS (OPTIMIZED)")
print("="*60)
print("")

if len(trades) > 0:
    trades_df = pd.DataFrame(trades)
    
    total = len(trades_df)
    wins = len(trades_df[trades_df['result'] == 'WIN'])
    losses = len(trades_df[trades_df['result'] == 'LOSS'])
    wr = (wins / total * 100) if total > 0 else 0
    
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    net_pnl = trades_df['pnl'].sum()
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
    
    print(f"Total Trades: {total}")
    print(f"Wins: {wins} ({wr:.1f}%)")
    print(f"Losses: {losses}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Net P&L: {net_pnl:.4f} ({net_pnl*10000:.1f} pips)")
    print(f"Avg Win: {avg_win:.4f} ({avg_win*10000:.1f} pips)")
    print(f"Avg Loss: {avg_loss:.4f} ({avg_loss*10000:.1f} pips)")
    print(f"Trades/Month: {total/10:.1f}")
    print("")
    
    # Compare to EURUSD
    print("📈 COMPARISON:")
    print(f"   EURUSD: 7 trades, 57.1% WR, 2.58 PF, 0.7/month")
    print(f"   GBPUSD: {total} trades, {wr:.1f}% WR, {pf:.2f} PF, {total/10:.1f}/month")
    print("")
    
    # Verdict
    print("🎯 VERDICT:")
    if pf >= 2.0 and wr >= 55 and total >= 5:
        print("   ✅ GBPUSD APPROVED!")
        print("   Strategy works on GBPUSD with optimized params")
        print("   Ready to add as 2nd pair")
    elif pf >= 1.5 and wr >= 50:
        print("   ⚠️ MARGINAL - Consider further optimization")
    else:
        print("   ❌ FAILED - Do not add GBPUSD")
        print("   Parameters need more work or pair not suitable")
    
    print("")
    print("💡 GROK'S OPTIMIZATIONS APPLIED:")
    print("   • BB 2.5 SD (reduced false signals)")
    print("   • RSI 25/75 (stricter extremes)")
    print("   • ADX <30 (better trend avoidance)")
    
else:
    print("❌ No trades generated!")
    print("   Strategy too restrictive - consider loosening filters")

print("")
print("="*60)
