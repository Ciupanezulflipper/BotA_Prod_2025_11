import sys

with open(sys.argv[1], 'r') as f:
    content = f.read()

# Find and replace the tg_send section
old_code = '''            result = subprocess.run(
                ["python3", tg_send, msg],
                capture_output=True, text=True
            )'''

new_code = '''            # Send with 3 retries
            for attempt in range(3):
                result = subprocess.run(
                    ["python3", tg_send, msg],
                    capture_output=True, text=True, timeout=30
                )
                
                if "SUCCESS" in result.stdout:
                    break
                elif attempt < 2:
                    print(f"⚠️ Send attempt {attempt+1} failed, retrying in 10s...")
                    import time
                    time.sleep(10)'''

content = content.replace(old_code, new_code)

with open(sys.argv[1], 'w') as f:
    f.write(content)

print("✅ Fixed!")
