# Add atomic writes to offline_queue_system.py
import os
from pathlib import Path

queue_file = Path.home() / 'bot-a' / 'tools' / 'offline_queue_system.py'

with open(queue_file, 'r') as f:
    content = f.read()

# Add atomic write function
atomic_func = '''
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
'''

# Insert after imports
if 'def atomic_write' not in content:
    import_end = content.find('\ndef ')
    content = content[:import_end] + '\n' + atomic_func + content[import_end:]
    
    # Replace json.dump with atomic_write
    content = content.replace(
        'with open(filepath, "w") as f:\n        json.dump(data, f)',
        'atomic_write(filepath, json.dumps(data))'
    )

with open(queue_file, 'w') as f:
    f.write(content)

print("✅ Atomic queue writes added")
