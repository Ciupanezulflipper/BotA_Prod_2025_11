path = "/data/data/com.termux/files/home/BotA/tools/alerts_to_trades.py"
with open(path) as f:
    src = f.read()

# Add --since argument
old_arg = '    ap.add_argument("--spread", type=float, default=1.5)'
new_arg = '''    ap.add_argument("--spread", type=float, default=1.5)
    ap.add_argument("--since",  default="", help="Only process signals after this UTC datetime e.g. 2026-02-24T00:00:00")'''
src = src.replace(old_arg, new_arg)

# Add filter after timestamp parse
old_filter = '    df = df.dropna(subset=["timestamp"])'
new_filter = '''    df = df.dropna(subset=["timestamp"])
    if args.since:
        from datetime import timezone
        since_dt = pd.to_datetime(args.since, utc=True, errors="coerce")
        if since_dt is not pd.NaT:
            df = df[df["timestamp"] >= since_dt]
            print(f"[since] Filtered to {len(df)} signals after {since_dt.isoformat()}")'''
src = src.replace(old_filter, new_filter)

with open(path, 'w') as f:
    f.write(src)
print("PATCHED OK")
