with open('runner_confluence.py', 'r') as f:
    content = f.read()

# Find and replace position size references
import re

# Replace 0.02 lots with 0.006 lots
content = re.sub(r'0\.02\s*lots', '0.006 lots', content, flags=re.IGNORECASE)
content = re.sub(r'Position:\s*0\.02', 'Position: 0.006', content)

# If there's a position_size variable
content = re.sub(r'position_size\s*=\s*0\.02', 'position_size = 0.006', content)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ Position size updated: 0.02 → 0.006 lots")
