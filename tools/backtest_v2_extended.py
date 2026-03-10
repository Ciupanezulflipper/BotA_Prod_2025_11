#!/usr/bin/env python3
"""
Extended backtest on 5000 bars
More statistically significant results
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Load 5000 bar data
data_file = Path.home() / "bot-a" / "data" / "EURUSD_H1_5000.csv"

print("📊 EXTENDED BACKTEST - 5000 BARS")
print("="*60)
print("")

df = pd.read_csv(data_file)

# Convert column names
for col in ['open', 'high', 'low', 'close']:
    if col not in df.columns:
        df[col] = df[col[0]]  # Map o,h,l,c to full names

print(f"✅ Loaded {len(df)} bars")
print(f"📅 Range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
print("")

# Calculate indicators
print("📈 Calculating indicators...")

# Bollinger Bands
df['sma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2)
df['bb_lower'] = df['sma20'] - (df['std20'] * 2)
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

# Run V2 strategy
print("🧪 Running V2 Bollinger + ADX strategy...")
print("")

trades = []
in_trade = False
entry_price = 0
entry_type = None
sl = 0
tp = 0

for i in range(100, len(df)):  # Skip first 100 for indicator warmup
    row = df.iloc[i]
    
    # Skip if any indicator is NaN
    if pd.isna(row['bb_position']) or pd.isna(row['rsi14']) or pd.isna(row['adx']):
        continue
    
    # Volatility filter
    if row['volatility'] < 0.25:
        continue
    
    # ADX filter (skip trending markets)
    if row['adx'] > 25:
        continue
    
    # Entry logic
    if not in_trade:
        # BUY: Oversold
        if row['bb_position'] < 0.2 and row['rsi14'] < 40:
            entry_price = row['close']
            entry_type = 'BUY'
            in_trade = True
            sl = entry_price - (row['atr14'] * 1.5)
            tp = row['sma20']
            
        # SELL: Overbought
        elif row['bb_position'] > 0.8 and row['rsi14'] > 60:
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
                trades.append({'type': 'BUY', 'result': 'LOSS', 'pnl': pnl, 'bars_held': len(trades)})
                in_trade = False
            elif row['close'] >= tp:
                pnl = tp - entry_price
                trades.append({'type': 'BUY', 'result': 'WIN', 'pnl': pnl, 'bars_held': len(trades)})
                in_trade = False
        
        elif entry_type == 'SELL':
            if row['high'] >= sl:
                pnl = entry_price - sl
                trades.append({'type': 'SELL', 'result': 'LOSS', 'pnl': pnl, 'bars_held': len(trades)})
                in_trade = False
            elif row['close'] <= tp:
                pnl = entry_price - tp
                trades.append({'type': 'SELL', 'result': 'WIN', 'pnl': pnl, 'bars_held': len(trades)})
                in_trade = False

# Calculate metrics
print("="*60)
print("📊 EXTENDED BACKTEST RESULTS (5000 bars)")
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
    
    # Calculate max drawdown
    cumulative = trades_df['pnl'].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_dd = drawdown.min()
    max_dd_pct = (max_dd / 0.01) * 100 if max_dd < 0 else 0  # Assuming 0.01 starting equity
    
    print(f"Total Trades: {total}")
    print(f"Wins: {wins} ({wr:.1f}%)")
    print(f"Losses: {losses}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Net P&L: {net_pnl:.4f} ({net_pnl*10000:.1f} pips)")
    print(f"Avg Win: {avg_win:.4f} ({avg_win*10000:.1f} pips)")
    print(f"Avg Loss: {avg_loss:.4f} ({avg_loss*10000:.1f} pips)")
    print(f"Max Drawdown: {max_dd:.4f} ({max_dd_pct:.1f}%)")
    print("")
    
    # Verdict
    print("🎯 VERDICT:")
    if total >= 100 and pf >= 1.3 and wr >= 50:
        print("   ✅ STRONG EDGE - Large sample confirms strategy!")
    elif total >= 50 and pf >= 1.2 and wr >= 45:
        print("   ⚠️ WEAK EDGE - Strategy marginal but tradeable")
    elif total < 30:
        print("   ⚠️ INSUFFICIENT DATA - Need more trades for confidence")
    else:
        print("   ❌ NO EDGE - Strategy does not hold up")
    
    print("")
    print("📈 COMPARISON TO ORIGINAL BACKTEST:")
    print(f"   Original (1000 bars): 4 trades, 50% WR, 2.38 PF")
    print(f"   Extended (5000 bars): {total} trades, {wr:.1f}% WR, {pf:.2f} PF")
    
    if total >= 20:
        wr_diff = wr - 50
        pf_diff = pf - 2.38
        print("")
        print(f"   WR change: {wr_diff:+.1f}% {'✅' if wr_diff >= -5 else '⚠️'}")
        print(f"   PF change: {pf_diff:+.2f} {'✅' if pf_diff >= -0.3 else '⚠️'}")
    
else:
    print("❌ No trades generated!")
    print("   Strategy too restrictive or data quality issue")

print("")
print("="*60)
print("✅ Extended backtest complete!")
