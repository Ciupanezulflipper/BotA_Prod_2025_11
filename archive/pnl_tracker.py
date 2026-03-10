#!/usr/bin/env python3
"""
Live Performance Tracker
Logs all signals and calculates real-time metrics
"""

import json
import csv
from datetime import datetime, timezone
from pathlib import Path

TRACKER_FILE = Path.home() / "bot-a" / "logs" / "live_trades.csv"

def log_signal(pair, action, entry, sl, tp, reason):
    """Log a new signal"""
    
    # Create file if doesn't exist
    if not TRACKER_FILE.exists():
        with open(TRACKER_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'pair', 'action', 'entry', 'sl', 'tp', 'reason', 'status', 'exit', 'pnl'])
    
    # Append signal
    with open(TRACKER_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            pair,
            action,
            entry,
            sl,
            tp,
            reason,
            'OPEN',
            '',
            ''
        ])
    
    print(f"✅ Logged {action} signal for {pair}")

def get_stats():
    """Get current performance stats"""
    
    if not TRACKER_FILE.exists():
        return {"total": 0, "open": 0, "closed": 0, "wins": 0, "losses": 0, "wr": 0, "pf": 0}
    
    import pandas as pd
    df = pd.read_csv(TRACKER_FILE)
    
    total = len(df)
    open_trades = len(df[df['status'] == 'OPEN'])
    closed = len(df[df['status'].isin(['WIN', 'LOSS'])])
    wins = len(df[df['status'] == 'WIN'])
    losses = len(df[df['status'] == 'LOSS'])
    
    wr = (wins / closed * 100) if closed > 0 else 0
    
    # Calculate PF
    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
    gross_profit = df[df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    return {
        "total": total,
        "open": open_trades,
        "closed": closed,
        "wins": wins,
        "losses": losses,
        "wr": round(wr, 1),
        "pf": round(pf, 2)
    }

if __name__ == "__main__":
    stats = get_stats()
    print(f"\n📊 LIVE PERFORMANCE:")
    print(f"   Total Signals: {stats['total']}")
    print(f"   Open: {stats['open']}")
    print(f"   Closed: {stats['closed']}")
    print(f"   Wins: {stats['wins']} / Losses: {stats['losses']}")
    print(f"   Win Rate: {stats['wr']}%")
    print(f"   Profit Factor: {stats['pf']}")
