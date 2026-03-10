#!/usr/bin/env python3
"""
Add volatility + H4 filters to existing runner_confluence.py
WITHOUT changing core logic
"""

# Read current runner
with open('runner_confluence.py', 'r') as f:
    lines = f.readlines()

# Find where we calculate action
for i, line in enumerate(lines):
    if 'action, score, reason = _score_stub(df)' in line:
        # Insert filters RIGHT AFTER getting the action
        filter_code = '''
    
    # FILTERS (V2 Enhancement)
    # 1. Volatility Filter
    volatility = (df["c"].std() / df["c"].mean()) * 100
    if volatility < 0.3 and action != "WAIT":
        action = "WAIT"
        reason = f"Filtered: Low volatility ({volatility:.3f}% < 0.3%)"
        score = 0
    
    # 2. H4 Trend Filter (optional - costs 1 extra API call)
    # Uncomment below to enable:
    # if action != "WAIT":
    #     import requests
    #     h4_url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=4h&outputsize=20&apikey={api_key}"
    #     h4_resp = requests.get(h4_url, timeout=10)
    #     h4_data = h4_resp.json()
    #     if 'values' in h4_data:
    #         h4_df = pd.DataFrame(h4_data['values'])
    #         h4_df['close'] = h4_df['close'].astype(float)
    #         h4_sma = h4_df['close'].rolling(20).mean().iloc[0]
    #         h4_price = float(h4_df['close'].iloc[0])
    #         
    #         if action == "BUY" and h4_price < h4_sma:
    #             action = "WAIT"
    #             reason = "Filtered: H4 downtrend conflicts with BUY"
    #         elif action == "SELL" and h4_price > h4_sma:
    #             action = "WAIT"
    #             reason = "Filtered: H4 uptrend conflicts with SELL"
'''
        
        lines.insert(i + 1, filter_code)
        break

# Write back
with open('runner_confluence.py', 'w') as f:
    f.writelines(lines)

print("✅ Filters added to runner_confluence.py!")
print("\n📋 What was added:")
print("  1. Volatility filter (< 0.3% = WAIT)")
print("  2. H4 trend filter (commented out - costs 1 API call)")
print("\n🔧 To enable H4 filter:")
print("  Edit runner_confluence.py and uncomment lines with 'h4_'")
