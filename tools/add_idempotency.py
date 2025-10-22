import hashlib
import json
from pathlib import Path

def generate_signal_id(timestamp, pair, action, entry):
    """Generate unique SHA-256 hash for signal"""
    key = f"{timestamp}|{pair}|{action}|{entry}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def add_id_to_queue():
    """Add IDs to existing queue files"""
    queue_dir = Path.home() / "bot-a" / "queue"
    
    for file in queue_dir.glob("signal_*.json"):
        with open(file, 'r') as f:
            data = json.load(f)
        
        # Add ID if not present
        if 'signal_id' not in data:
            data['signal_id'] = generate_signal_id(
                data['timestamp'],
                data['pair'],
                data['action'],
                data['entry']
            )
            
            with open(file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Added ID to {file.name}: {data['signal_id']}")

if __name__ == "__main__":
    add_id_to_queue()
    print("\n✅ Idempotency keys added to all queued signals!")
