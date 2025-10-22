with open('runner_v2_bollinger.py', 'r') as f:
    content = f.read()

# Find and replace _score_stub function
v2_strategy = '''def _score_stub(df):
    """V2: Bollinger Bands Mean Reversion"""
    
    current = df.iloc[-1]
    
    # Bollinger Bands
    sma20 = df['c'].rolling(20).mean().iloc[-1]
    std20 = df['c'].rolling(20).std().iloc[-1]
    bb_upper = sma20 + (std20 * 2)
    bb_lower = sma20 - (std20 * 2)
    bb_position = (current['c'] - bb_lower) / (bb_upper - bb_lower)
    
    # RSI
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # Volatility
    volatility = (df['c'].rolling(20).std() / df['c'].rolling(20).mean()).iloc[-1] * 100
    
    if volatility < 0.25:
        return "WAIT", 0, f"Vol {volatility:.3f}%"
    
    # BUY: Oversold
    if bb_position < 0.2 and rsi < 40:
        score = (0.2 - bb_position) * 2
        return "BUY", score, f"BB oversold ({bb_position:.2f}, RSI {rsi:.0f})"
    
    # SELL: Overbought
    elif bb_position > 0.8 and rsi > 60:
        score = (bb_position - 0.8) * 2
        return "SELL", score, f"BB overbought ({bb_position:.2f}, RSI {rsi:.0f})"
    
    return "WAIT", 0, f"No extreme (pos={bb_position:.2f})"
'''

# Replace the function
import re
pattern = r'def _score_stub\(df\):.*?(?=\n(?:def |if __name__))'
content = re.sub(pattern, v2_strategy.rstrip(), content, flags=re.DOTALL)

with open('runner_v2_bollinger.py', 'w') as f:
    f.write(content)

print("✅ V2 strategy installed!")
