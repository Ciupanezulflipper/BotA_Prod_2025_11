import sys

with open('runner_confluence.py', 'r') as f:
    content = f.read()

# Replace old SL/TP with conservative ATR
old_code = '''    # Calculate Stop Loss and Take Profit (1% risk, 2% reward = 1:2 R:R)
    last_price = float(df["c"].iloc[-1])

    if action == "BUY":
        stop_loss = round(last_price * 0.99, 5)  # 1% below entry
        take_profit = round(last_price * 1.02, 5)  # 2% above entry
        risk_reward = "1:2"
    elif action == "SELL":
        stop_loss = round(last_price * 1.01, 5)  # 1% above entry
        take_profit = round(last_price * 0.98, 5)  # 2% below entry
        risk_reward = "1:2"
    else:
        stop_loss = None
        take_profit = None
        risk_reward = None'''

new_code = '''    # Calculate SL/TP using Conservative ATR (optimized for mobile/small capital)
    from atr_sltp_conservative import calculate_atr, calculate_sltp_atr
    
    atr = calculate_atr(df, period=14)
    last_price = float(df["c"].iloc[-1])
    
    stop_loss, take_profit, risk_reward, sl_pips, tp_pips = calculate_sltp_atr(
        last_price=last_price,
        action=action,
        atr=atr,
        sl_multiplier=1.5,  # Conservative: 15-20 pips typical
        tp_multiplier=2.5,  # Quick wins: 30-40 pips typical
        max_sl_pips=20,     # Protect $200 capital
        max_tp_pips=40      # Realistic targets
    )'''

content = content.replace(old_code, new_code)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ Conservative ATR integrated!")
