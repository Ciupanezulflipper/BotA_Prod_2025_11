# Add London/NY session filter to runner

with open('runner_confluence.py', 'r') as f:
    content = f.read()

session_filter = '''
def is_trading_hours():
    """Only trade London/NY overlap: 13:00-17:00 UTC"""
    from datetime import datetime
    now = datetime.utcnow()
    hour = now.hour
    
    # London/NY overlap: 13:00-17:00 UTC
    if 13 <= hour < 17:
        # Skip first 15 min and last 30 min
        minute = now.minute
        if hour == 13 and minute < 15:
            return False, "too early in session"
        if hour == 16 and minute >= 30:
            return False, "too late in session"
        return True, "trading hours"
    else:
        return False, f"outside hours (now {hour:02d}:00 UTC)"

'''

if 'def is_trading_hours' not in content:
    # Add after check_news_blackout
    pos = content.find('def check_news_blackout')
    end_pos = content.find('\ndef ', pos + 10)
    content = content[:end_pos] + '\n' + session_filter + content[end_pos:]
    
    # Add call in run() before signal generation
    # Find where we check news blackout
    check_pos = content.find('news_ok, news_msg = check_news_blackout()')
    if check_pos > 0:
        # Insert session check right after news check
        insert_pos = content.find('\n', check_pos) + 1
        session_check = '''    # Session filter - London/NY only
    session_ok, session_msg = is_trading_hours()
    if not session_ok:
        print(f"⏰ {session_msg}")
        return 0
    
'''
        content = content[:insert_pos] + session_check + content[insert_pos:]
        
        with open('runner_confluence.py', 'w') as f:
            f.write(content)
        
        print("✅ Session filter added: London/NY overlap only (13:00-17:00 UTC)")
    else:
        print("⚠️ Could not find news check insertion point")
else:
    print("✅ Already has session filter")

print("\nVerify:")
print("grep -n 'is_trading_hours' ~/bot-a/tools/runner_confluence.py")
