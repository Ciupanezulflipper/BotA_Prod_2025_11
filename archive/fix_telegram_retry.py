import sys

with open(sys.argv[1], 'r') as f:
    lines = f.readlines()

# Find the subprocess.run for tg_send
for i, line in enumerate(lines):
    if 'result = subprocess.run' in line and i > 180:
        # Replace the next 3 lines with retry logic
        lines[i] = '            # Send with retry\n'
        lines[i+1] = '            for attempt in range(3):\n'
        lines[i+2] = '                result = subprocess.run(\n'
        lines.insert(i+3, '                    ["python3", tg_send, msg],\n')
        lines.insert(i+4, '                    capture_output=True, text=True, timeout=30\n')
        lines.insert(i+5, '                )\n')
        lines.insert(i+6, '                \n')
        lines.insert(i+7, '                if "SUCCESS" in result.stdout:\n')
        lines.insert(i+8, '                    break\n')
        lines.insert(i+9, '                elif attempt < 2:\n')
        lines.insert(i+10, '                    print(f"⚠️ Send failed (attempt {attempt+1}/3), retrying in 10s...")\n')
        lines.insert(i+11, '                    import time\n')
        lines.insert(i+12, '                    time.sleep(10)\n')
        break

with open(sys.argv[1], 'w') as f:
    f.writelines(lines)

print("✅ Retry logic added")
