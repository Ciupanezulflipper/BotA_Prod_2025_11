#!/usr/bin/env python3
"""Wrapper for runner with offline queue"""

import subprocess
import sys
from offline_queue_system import queue_signal, is_online
from datetime import datetime

result = subprocess.run(
    ["python3", "runner_confluence.py"] + sys.argv[1:],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)


# Safety: Don't queue if volatility too low
if "Volatility" in result.stdout and "0.2" in result.stdout:
    vol_str = [l for l in result.stdout.split('\n') if 'Volatility' in l]
    if vol_str:
        try:
            vol_val = float(vol_str[0].split('=')[1].split('%')[0].strip())
            if vol_val < 0.25:
                print(f"🚫 Volatility {vol_val:.3f}% too low, not queueing")
                sys.exit(0)
        except:
            pass

if not is_online() and ("Action: BUY" in result.stdout or "Action: SELL" in result.stdout):
    lines = result.stdout.split('\n')
    
    signal_data = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'pair': 'EURUSD',
        'action': 'UNKNOWN',
        'entry': 0,
        'sl': 0,
        'tp': 0,
        'sl_pips': 0,
        'tp_pips': 0,
        'volatility': 0,
        'score': 0,
        'reason': 'Offline'
    }
    
    for line in lines:
        if 'Action:' in line:
            signal_data['action'] = line.split('Action:')[1].strip()
        elif 'Score:' in line:
            signal_data['score'] = float(line.split('Score:')[1].strip())
    
    if signal_data['action'] in ['BUY', 'SELL']:
        queue_signal(signal_data)

sys.exit(result.returncode)
