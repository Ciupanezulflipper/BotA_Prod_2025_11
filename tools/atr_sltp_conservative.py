#!/usr/bin/env python3
"""
ATR-based SL/TP - Conservative Settings
Optimized for: $200 capital, mobile/Termux, intermittent internet
Strategy: Quick wins, tight stops, realistic targets
"""

import pandas as pd

def calculate_atr(df, period=14):
    """Calculate 14-period ATR"""
    df = df.copy()
    
    # True Range components
    df['h-l'] = df['h'] - df['l']
    df['h-pc'] = abs(df['h'] - df['c'].shift(1))
    df['l-pc'] = abs(df['l'] - df['c'].shift(1))
    
    # True Range = max of three
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    
    # ATR = 14-period average
    atr = df['tr'].rolling(window=period).mean().iloc[-1]
    
    return atr

def calculate_sltp_atr(last_price, action, atr, 
                       sl_multiplier=1.5, tp_multiplier=2.5,
                       max_sl_pips=20, max_tp_pips=40):
    """
    Conservative ATR method for mobile trading
    - Quick wins (30-40 pips)
    - Tight stops (15-20 pips)
    - Realistic for H1 EURUSD
    """
    if action not in ["BUY", "SELL"]:
        return None, None, None, None, None
    
    # Calculate distances
    sl_distance = atr * sl_multiplier
    tp_distance = atr * tp_multiplier
    
    # Convert pip caps to price
    max_sl_distance = max_sl_pips * 0.0001
    max_tp_distance = max_tp_pips * 0.0001
    
    # Apply caps
    sl_distance = min(sl_distance, max_sl_distance)
    tp_distance = min(tp_distance, max_tp_distance)
    
    # Calculate prices
    if action == "BUY":
        stop_loss = round(last_price - sl_distance, 5)
        take_profit = round(last_price + tp_distance, 5)
    else:  # SELL
        stop_loss = round(last_price + sl_distance, 5)
        take_profit = round(last_price - tp_distance, 5)
    
    # Calculate pips
    sl_pips = round(abs(last_price - stop_loss) / 0.0001, 1)
    tp_pips = round(abs(take_profit - last_price) / 0.0001, 1)
    
    # Risk:Reward
    risk_reward = f"1:{round(tp_pips / sl_pips, 1)}"
    
    return stop_loss, take_profit, risk_reward, sl_pips, tp_pips

if __name__ == "__main__":
    # Test with your current trade
    print("🎯 Conservative ATR Settings Test")
    print("=" * 50)
    print("\nYour Current Trade:")
    print("Entry: 1.16926")
    
    # Typical EURUSD ATR
    test_atr = 0.00055
    
    sl, tp, rr, sl_pips, tp_pips = calculate_sltp_atr(
        last_price=1.16926,
        action="BUY",
        atr=test_atr,
        sl_multiplier=1.5,
        tp_multiplier=2.5,
        max_sl_pips=20,
        max_tp_pips=40
    )
    
    print(f"\nATR: {test_atr:.5f} (55 pips)")
    print(f"\nCalculated:")
    print(f"  SL: 1.5 × ATR = {(test_atr * 1.5) / 0.0001:.1f} pips")
    print(f"  TP: 2.5 × ATR = {(test_atr * 2.5) / 0.0001:.1f} pips")
    print(f"\nCapped (Your Settings):")
    print(f"  🛑 SL: {sl} (-{sl_pips} pips)")
    print(f"  ✅ TP: {tp} (+{tp_pips} pips)")
    print(f"  ⚖️  R:R: {rr}")
    print(f"\nRisk: ${sl_pips * 0.02 * 10:.2f} (@ 0.02 lots)")
    print(f"Reward: ${tp_pips * 0.02 * 10:.2f} (@ 0.02 lots)")
    print(f"\nTime to TP: 2-4 hours (realistic!) ✅")
    print("=" * 50)
