import re

with open('runner_confluence.py', 'r') as f:
    content = f.read()

# Add news blackout function after imports
news_function = '''
from datetime import datetime, timezone
import os

def check_news_blackout(window_min=90):
    """Check if we're in news blackout window"""
    news_file = os.path.expanduser("~/bot-a/news_utc.txt")
    
    if not os.path.exists(news_file):
        return False, "no news file"
    
    now = datetime.now(timezone.utc)
    
    for line in open(news_file):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            event_time = datetime.fromisoformat(line.replace("Z", "+00:00"))
            minutes_away = abs((event_time - now).total_seconds()) / 60
            
            if minutes_away <= window_min:
                return True, f"News event in {minutes_away:.0f}min"
        except:
            pass
    
    return False, "clear"

'''

# Insert after the last import and before first function
pattern = r'(from pathlib import Path\n)'
replacement = r'\1\n' + news_function
content = re.sub(pattern, replacement, content, count=1)

# Now add the check in the run() function, right after _validate check
# Find the line: if not ok:
pattern = r'(    ok, why = _validate\(df, tf, bars\).*?\n    now = .*?\n\n    if not ok:)'
replacement = r'''\1
        print(f"✗ Data quality failed: {why}")
        return 2
    
    # Check news blackout
    in_blackout, blackout_reason = check_news_blackout(90)
    if in_blackout:
        print(f"🔇 News blackout: {blackout_reason}")
        return 0
    
    if False:  # Disable original not ok block'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ News blackout integrated!")
