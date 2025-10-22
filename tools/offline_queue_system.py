#!/usr/bin/env python3
"""
Offline Queue System - Critical for 6-hour dinner gap
Saves signals when no internet, sends when reconnected
"""

import json
import os
from pathlib import Path
from datetime import datetime
import requests

QUEUE_DIR = Path.home() / "bot-a" / "queue"
QUEUE_DIR.mkdir(exist_ok=True)


import tempfile
import shutil

def atomic_write(filepath, data):
    """Write atomically to prevent corruption"""
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filepath))
    try:
        with os.fdopen(temp_fd, 'w') as f:
            f.write(data)
        shutil.move(temp_path, filepath)
    except:
        os.unlink(temp_path)
        raise

def is_online():
    """Quick check if internet is available"""
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except:
        return False

def queue_signal(signal_data):
    cleanup_old_signals(100)
    import hashlib
    signal_id = hashlib.sha256(f"{signal_data["timestamp"]}|{signal_data["pair"]}|{signal_data["action"]}|{signal_data["entry"]}".encode()).hexdigest()[:16]
    signal_data["signal_id"] = signal_id
    """
    Save signal to queue when offline
    
    signal_data = {
        'timestamp': '2025-10-17 16:45:00',
        'pair': 'EURUSD',
        'action': 'BUY',
        'entry': 1.17089,
        'sl': 1.16926,
        'tp': 1.17362,
        'sl_pips': 16.3,
        'tp_pips': 27.3,
        'volatility': 0.37,
        'score': 0.21,
        'reason': 'last > SMA20 by >0.15%'
    }
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = QUEUE_DIR / f"signal_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(signal_data, f, indent=2)
    
    print(f"📥 Queued offline: {filename.name}")
    
    # Also log to text file for easy reading
    log_file = QUEUE_DIR / "offline_signals.log"
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Time: {signal_data['timestamp']}\n")
        f.write(f"Action: {signal_data['action']} {signal_data['pair']}\n")
        f.write(f"Entry: {signal_data['entry']}\n")
        f.write(f"SL: {signal_data['sl']} (-{signal_data['sl_pips']:.1f} pips)\n")
        f.write(f"TP: {signal_data['tp']} (+{signal_data['tp_pips']:.1f} pips)\n")
        f.write(f"Volatility: {signal_data['volatility']:.3f}%\n")
        f.write(f"Reason: {signal_data['reason']}\n")

def send_queued_signals():
    """Send all queued signals when internet returns"""
    
    if not is_online():
        print("📴 Still offline, skipping send")
        return
    
    files = sorted(QUEUE_DIR.glob("signal_*.json"))
    
    if not files:
        print("📭 No queued signals")
        return
    
    print(f"📬 Found {len(files)} queued signals, sending...")
    
    # Build summary message
    summary = f"🔄 OFFLINE SIGNALS SUMMARY\n"
    summary += f"Reconnected: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n"
    summary += f"Signals missed: {len(files)}\n\n"
    
    for i, file in enumerate(files, 1):
        with open(file, 'r') as f:
            data = json.load(f)
        
        summary += f"Signal #{i} ({data['timestamp']})\n"
        summary += f"  {data['action']} @ {data['entry']}\n"
        summary += f"  SL: {data['sl']} / TP: {data['tp']}\n"
        summary += f"  Vol: {data['volatility']:.3f}%\n\n"
    
    # Send via tg_send
    import subprocess
    tg_script = Path.home() / "bot-a" / "tools" / "tg_send.py"
    
    result = subprocess.run(
        ["python3", str(tg_script), summary],
        capture_output=True, text=True, timeout=30
    )
    
    if "SUCCESS" in result.stdout:
        print(f"✅ Sent summary to Telegram")
        
        # Archive sent signals
        archive_dir = QUEUE_DIR / "sent"
        archive_dir.mkdir(exist_ok=True)
        
        for file in files:
            file.rename(archive_dir / file.name)
        
        print(f"📦 Archived {len(files)} signals")
    else:
        print(f"❌ Send failed: {result.stdout}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        # Called with: python3 offline_queue_system.py send
        send_queued_signals()
    else:
        # Test
        print("🧪 Testing offline queue...")
        
        test_signal = {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'pair': 'EURUSD',
            'action': 'BUY',
            'entry': 1.17089,
            'sl': 1.16926,
            'tp': 1.17362,
            'sl_pips': 16.3,
            'tp_pips': 27.3,
            'volatility': 0.37,
            'score': 0.21,
            'reason': 'Test signal'
        }
        
        queue_signal(test_signal)
        
        print("\nTo send queued signals:")
        print("  python3 offline_queue_system.py send")

def cleanup_old_signals(max_signals=100):
    """Keep only the most recent signals to prevent overflow"""
    import os
    from pathlib import Path
    
    queue_dir = Path.home() / "bot-a" / "queue"
    signals = sorted(queue_dir.glob("signal_*.json"), key=os.path.getmtime)
    
    if len(signals) > max_signals:
        to_delete = signals[:-max_signals]
        for file in to_delete:
            file.unlink()
            print(f"🗑️ Deleted old signal: {file.name}")
        
        print(f"✅ Cleaned up {len(to_delete)} old signals")
