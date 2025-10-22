import sys

with open(sys.argv[1], 'r') as f:
    lines = f.readlines()

# Find where we format the Telegram message
for i, line in enumerate(lines):
    if 'msg += f"📏 Position: 0.02 lots' in line:
        # Add SL/TP calculation right before the message
        insert_pos = i - 1
        
        # Find the line with action/score/reason to get context
        for j in range(i-10, i):
            if 'action, score, reason = _score_stub' in lines[j]:
                # Insert SL/TP calculation after we have the action
                sl_tp_code = '''
    # Calculate Stop Loss and Take Profit
    last_price = float(df['close'].iloc[-1])
    
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
        risk_reward = None
    
'''
                lines.insert(j + 1, sl_tp_code)
                
                # Now update the Telegram message to include SL/TP
                for k in range(i, len(lines)):
                    if 'msg += f"🛡️ Risk: 2% ($4)"' in lines[k]:
                        lines[k] = lines[k].rstrip() + '\n'
                        if action != "WAIT":
                            lines.insert(k + 1, '            msg += f"\\n🎯 Entry: {last_price}\\n"\n')
                            lines.insert(k + 2, '            msg += f"🛑 Stop Loss: {stop_loss}\\n"\n')
                            lines.insert(k + 3, '            msg += f"✅ Take Profit: {take_profit}\\n"\n')
                            lines.insert(k + 4, '            msg += f"⚖️ R:R = {risk_reward}"\n')
                        break
                break
        break

with open(sys.argv[1], 'w') as f:
    f.writelines(lines)

print("✅ SL/TP automation added")
