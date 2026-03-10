# Direct line-by-line replacement

with open('runner_confluence.py', 'r') as f:
    lines = f.readlines()

# Find the line with "# Calculate Stop Loss"
for i, line in enumerate(lines):
    if '# Calculate Stop Loss and Take Profit (1% risk' in line:
        # Replace from this line through the else block (17 lines)
        new_code = [
            '    # Calculate SL/TP using Conservative ATR\n',
            '    from atr_sltp_conservative import calculate_atr, calculate_sltp_atr\n',
            '    \n',
            '    atr = calculate_atr(df, period=14)\n',
            '    last_price = float(df["c"].iloc[-1])\n',
            '    \n',
            '    stop_loss, take_profit, risk_reward, sl_pips, tp_pips = calculate_sltp_atr(\n',
            '        last_price=last_price,\n',
            '        action=action,\n',
            '        atr=atr,\n',
            '        sl_multiplier=1.5,\n',
            '        tp_multiplier=2.5,\n',
            '        max_sl_pips=20,\n',
            '        max_tp_pips=40\n',
            '    )\n'
        ]
        
        # Replace 17 lines (from "# Calculate" to "risk_reward = None")
        lines[i:i+17] = new_code
        break

with open('runner_confluence.py', 'w') as f:
    f.writelines(lines)

print("✅ ATR code inserted!")
