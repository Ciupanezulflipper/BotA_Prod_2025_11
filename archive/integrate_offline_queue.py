#!/usr/bin/env python3
"""Add offline queue capability to runner"""

with open('runner_confluence.py', 'r') as f:
    lines = f.readlines()

# Add import at top
for i, line in enumerate(lines):
    if 'import subprocess' in line and i < 50:
        lines.insert(i + 1, 'from offline_queue_system import queue_signal, is_online\n')
        break

# Find Telegram send section and add offline handling
for i, line in enumerate(lines):
    if '# Send via tg_send.py' in line:
        # Insert offline check before sending
        offline_code = '''
            # Check if online
            if not is_online():
                # Queue signal for later
                signal_data = {
                    'timestamp': now,
                    'pair': pair,
                    'action': action,
                    'entry': last_price,
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
                return 0
            
'''
        lines.insert(i, offline_code)
        break

with open('runner_confluence.py', 'w') as f:
    f.writelines(lines)

print("✅ Offline queue integrated into runner!")
