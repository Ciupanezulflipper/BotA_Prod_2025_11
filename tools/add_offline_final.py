with open('runner_confluence.py', 'r') as f:
    lines = f.readlines()

# Find line with 'import pandas as pd'
for i, line in enumerate(lines):
    if 'import pandas as pd' in line:
        # Add imports right after pandas
        lines.insert(i + 1, '\n# Offline queue system\n')
        lines.insert(i + 2, 'import sys\n')
        lines.insert(i + 3, 'sys.path.insert(0, "/data/data/com.termux/files/home/bot-a/tools")\n')
        lines.insert(i + 4, 'from offline_queue_system import queue_signal, is_online\n')
        break

# Find where Telegram send happens
for i, line in enumerate(lines):
    if 'if "CLEAR TO TRADE" in risk_check.stdout and action != "WAIT":' in line:
        # Add offline check right after this if
        offline_check = '''
            # Check internet before sending
            if not is_online():
                signal_data = {
                    'timestamp': now,
                    'pair': pair,
                    'action': action,
                    'entry': float(df["c"].iloc[-1]),
                    'sl': stop_loss,
                    'tp': take_profit,
                    'sl_pips': sl_pips,
                    'tp_pips': tp_pips,
                    'volatility': volatility,
                    'score': score,
                    'reason': reason
                }
                queue_signal(signal_data)
                print("📴 Offline: Signal queued")
            else:
'''
        lines[i] = lines[i].rstrip() + '\n' + offline_check
        break

with open('runner_confluence.py', 'w') as f:
    f.writelines(lines)

print("✅ Done!")
