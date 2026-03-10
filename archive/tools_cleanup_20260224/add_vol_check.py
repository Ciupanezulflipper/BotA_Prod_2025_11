with open('runner_with_offline.py', 'r') as f:
    content = f.read()

# Add vol check after getting result
vol_check = '''
# Safety: Don't queue if volatility too low
if "Volatility" in result.stdout and "0.2" in result.stdout:
    vol_str = [l for l in result.stdout.split('\\n') if 'Volatility' in l]
    if vol_str:
        try:
            vol_val = float(vol_str[0].split('=')[1].split('%')[0].strip())
            if vol_val < 0.25:
                print(f"🚫 Volatility {vol_val:.3f}% too low, not queueing")
                sys.exit(0)
        except:
            pass
'''

# Insert before queueing logic
content = content.replace('if not is_online()', vol_check + '\nif not is_online()')

with open('runner_with_offline.py', 'w') as f:
    f.write(content)
