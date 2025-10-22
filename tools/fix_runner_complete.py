import re

with open('runner_confluence.py', 'r') as f:
    content = f.read()

# 1. Add imports at top (after existing imports)
imports_to_add = '''
# Safety systems
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from risk_manager import check_risk, check_trade_cap

def check_news_blackout(window_min=90):
    """Check if we're in news blackout window"""
    from datetime import datetime, timezone
    import os
    
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
                return True, f"News in {minutes_away:.0f}min"
        except:
            pass
    return False, "clear"

'''

# Find position after imports (before first function)
pattern = r'(from pathlib import Path\n)'
if pattern not in content:
    # Try alternate location
    pattern = r'(import os\n)'

content = re.sub(pattern, r'\1' + imports_to_add, content, count=1)

# 2. Add trade cap check in run() function
# Find where we call check_news_blackout (line ~154)
trade_cap_check = '''
    # Trade cap check
    cap_ok, cap_msg = check_trade_cap(3)
    if not cap_ok:
        print(f"🛑 {cap_msg}")
        return 0
    
'''

# Insert before news blackout check
pattern = r'(    in_blackout, blackout_reason = check_news_blackout)'
content = re.sub(pattern, trade_cap_check + r'\1', content)

# 3. Fix the broken news blackout check (it's calling but function might be missing)
# Make sure the check actually returns properly
pattern = r'(    in_blackout, blackout_reason = check_news_blackout\(90\)\n)'
replacement = r'\1    if in_blackout:\n        print(f"🔇 News blackout: {blackout_reason}")\n        return 0\n\n'
content = re.sub(pattern, replacement, content)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ Fixed all gaps!")
print("   - News blackout function defined")
print("   - Trade cap integrated")
print("   - Risk manager imported")
