# Add to runner_confluence.py

validation_code = '''
def validate_api_data(data, max_age_seconds=300):
    """Validate data quality and freshness"""
    import time
    
    if not data or len(data) < 20:
        return False, "insufficient data"
    
    # Check data freshness (< 5 minutes old)
    try:
        latest_time = data.index[-1]
        age = time.time() - latest_time.timestamp()
        if age > max_age_seconds:
            return False, f"stale data ({age:.0f}s old)"
    except:
        pass  # Skip if timestamp check fails
    
    # Check for obvious bad data
    if data['c'].isnull().sum() > len(data) * 0.1:
        return False, "too many null values"
    
    return True, "ok"
'''

with open('runner_confluence.py', 'r') as f:
    content = f.read()

if 'def validate_api_data' not in content:
    # Add after imports
    pos = content.find('def check_news_blackout')
    content = content[:pos] + validation_code + '\n' + content[pos:]
    
    # Add call after data fetch (before _validate)
    content = content.replace(
        'df = _to_df(rows)\n\n    ok, why = _validate',
        '''df = _to_df(rows)
    
    # API data quality check
    api_ok, api_why = validate_api_data(df)
    if not api_ok:
        print(f"⚠️ API data issue: {api_why}")
        # Continue anyway but log the issue
    
    ok, why = _validate'''
    )
    
    with open('runner_confluence.py', 'w') as f:
        f.write(content)
    
    print("✅ API validation added")
else:
    print("✅ Already has validation")
