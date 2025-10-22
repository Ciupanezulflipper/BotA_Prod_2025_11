with open('runner_confluence.py', 'r') as f:
    content = f.read()

# Fix the ambiguous DataFrame check
content = content.replace(
    'if not data or len(data) < 20:',
    'if data is None or len(data) < 20:'
)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ Fixed DataFrame validation bug")
