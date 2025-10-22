# Add ADX filter to V2 Bollinger strategy

with open('runner_confluence.py', 'r') as f:
    content = f.read()

if 'calculate_adx' in content:
    print("✅ Already has ADX filter")
else:
    # Find the _score_stub function
    score_pos = content.find('def _score_stub')
    
    if score_pos < 0:
        print("⚠️ Could not find _score_stub function")
    else:
        # Find the volatility check inside _score_stub
        vol_check = 'if volatility < 0.25:'
        vol_pos = content.find(vol_check, score_pos)
        
        if vol_pos < 0:
            print("⚠️ Could not find volatility check")
        else:
            # Find the line after volatility check (the return statement)
            return_pos = content.find('return "WAIT"', vol_pos)
            next_line_pos = content.find('\n', return_pos) + 1
            
            # ADX code to insert
            adx_code = '''
    # ADX filter (avoid mean reversion in strong trends)
    high = df['h']
    low = df['l']
    close = df['c']
    
    # Simple ADX calculation (period=14)
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    
    atr_adx = tr.rolling(14).mean()
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
    
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_adx)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_adx)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(14).mean().iloc[-1]
    
    # Skip if trending market (ADX > 25)
    if adx > 25:
        return "WAIT", 0, f"ADX {adx:.1f} (trending - skip mean reversion)"
    
'''
            
            # Insert ADX code
            content = content[:next_line_pos] + adx_code + content[next_line_pos:]
            
            with open('runner_confluence.py', 'w') as f:
                f.write(content)
            
            print("✅ ADX filter added")
            print("   Skips mean reversion when ADX > 25 (trending market)")

print("\nVerify:")
print("grep -n 'ADX\\|adx' ~/bot-a/tools/runner_confluence.py | head -5")
