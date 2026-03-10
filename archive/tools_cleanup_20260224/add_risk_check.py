with open('runner_confluence.py', 'r') as f:
    content = f.read()

# Update import
content = content.replace(
    'from risk_manager import check_trade_cap',
    'from risk_manager import check_trade_cap, can_trade'
)

# Add can_trade check before trade cap
risk_check = '''
    # Daily loss limit check
    if not can_trade():
        print("🛑 Daily loss limit hit - trading suspended")
        return 0
    
'''

# Insert before trade cap check
content = content.replace(
    '    # Trade cap check\n    cap_ok',
    risk_check + '    # Trade cap check\n    cap_ok'
)

with open('runner_confluence.py', 'w') as f:
    f.write(content)

print("✅ Risk state check added!")
