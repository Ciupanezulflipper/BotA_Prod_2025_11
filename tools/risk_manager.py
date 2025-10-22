#!/usr/bin/env python3
"""
Risk Manager for BotA - Protects capital with strict rules
Designed for $200 account with 0.3 lot max
"""

from datetime import datetime
from pathlib import Path
import json

# CRITICAL SETTINGS (Conservative for $200 account)
ACCOUNT_BALANCE = 200.0
MAX_POSITION_SIZE = 0.3
MAX_RISK_PER_TRADE = 0.015  # 2% = $4 max loss per trade
MAX_DAILY_LOSS = 0.05  # 6% = $12 max loss per day
MAX_CONCURRENT_TRADES = 1  # Only 1 trade at a time
MIN_WIN_RATE_REQUIRED = 0.60  # Need 60% to continue

STATE_FILE = Path.home() / "bot-a" / "logs" / ".risk_state.json"


def load_risk_state():
    """Load current risk state"""
    if not STATE_FILE.exists():
        return {
            "date": str(datetime.now().date()),
            "balance": ACCOUNT_BALANCE,
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_today": 0.0,
            "open_positions": 0
        }
    
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    
    # Reset daily stats if new day
    if state.get("date") != str(datetime.now().date()):
        state.update({
            "date": str(datetime.now().date()),
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_today": 0.0
        })
    
    return state


def save_risk_state(state):
    """Save risk state"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def can_trade():
    """Check if we can take a new trade"""
    state = load_risk_state()
    
    reasons = []
    
    # Check 1: Daily loss limit
    if state["pnl_today"] <= -(ACCOUNT_BALANCE * MAX_DAILY_LOSS):
        reasons.append(f"🛑 DAILY LOSS LIMIT HIT: ${abs(state['pnl_today']):.2f} (max: ${ACCOUNT_BALANCE * MAX_DAILY_LOSS:.2f})")
        return False, reasons
    
    # Check 2: Open positions limit
    if state["open_positions"] >= MAX_CONCURRENT_TRADES:
        reasons.append(f"⏸️  MAX POSITIONS: {state['open_positions']}/{MAX_CONCURRENT_TRADES}")
        return False, reasons
    
    # Check 3: Win rate check (after 10 trades)
    if state["trades_today"] >= 10:
        win_rate = state["wins_today"] / state["trades_today"]
        if win_rate < MIN_WIN_RATE_REQUIRED:
            reasons.append(f"📉 LOW WIN RATE: {win_rate*100:.1f}% (need {MIN_WIN_RATE_REQUIRED*100:.0f}%)")
            return False, reasons
    
    # All checks passed
    return True, ["✅ All risk checks passed"]


def calculate_position_size(stop_loss_pips=20):
    """Calculate safe position size based on risk"""
    state = load_risk_state()
    
    max_risk_dollars = state["balance"] * MAX_RISK_PER_TRADE
    
    # For EURUSD: 1 pip = $0.10 per 0.01 lot
    # $4 max risk / $0.10 per pip / 20 pip SL = 2 lots
    # But cap at 0.3 for safety
    
    pip_value_per_lot = 10.0  # $10 per pip for 1 lot EURUSD
    calculated_lots = max_risk_dollars / (stop_loss_pips * pip_value_per_lot)
    
    # Cap at maximum allowed
    safe_lots = min(calculated_lots, MAX_POSITION_SIZE)
    
    return round(safe_lots, 2)


def get_risk_report():
    """Get current risk status"""
    state = load_risk_state()
    
    win_rate = (state["wins_today"] / state["trades_today"] * 100) if state["trades_today"] > 0 else 0
    
    remaining_risk = (ACCOUNT_BALANCE * MAX_DAILY_LOSS) + state["pnl_today"]
    
    can_trade_now, reasons = can_trade()
    
    return {
        "balance": state["balance"],
        "pnl_today": state["pnl_today"],
        "trades_today": state["trades_today"],
        "win_rate": round(win_rate, 1),
        "remaining_daily_risk": round(remaining_risk, 2),
        "can_trade": can_trade_now,
        "reasons": reasons,
        "max_position": calculate_position_size()
    }


if __name__ == "__main__":
    print("=== BotA Risk Manager ===")
    print(f"💰 Account: ${ACCOUNT_BALANCE}")
    print(f"📊 Max Risk Per Trade: {MAX_RISK_PER_TRADE*100}% (${ACCOUNT_BALANCE * MAX_RISK_PER_TRADE})")
    print(f"🛑 Max Daily Loss: {MAX_DAILY_LOSS*100}% (${ACCOUNT_BALANCE * MAX_DAILY_LOSS})")
    print()
    
    report = get_risk_report()
    
    print(f"📈 Current Balance: ${report['balance']}")
    print(f"{'🟢' if report['pnl_today'] >= 0 else '🔴'} Today's P&L: ${report['pnl_today']:.2f}")
    print(f"📊 Trades Today: {report['trades_today']} (Win Rate: {report['win_rate']}%)")
    print(f"💵 Remaining Daily Risk: ${report['remaining_daily_risk']:.2f}")
    print(f"📏 Recommended Position: {report['max_position']} lots")
    print()
    
    if report['can_trade']:
        print("✅ CLEAR TO TRADE")
    else:
        print("🛑 TRADING HALTED")
    
    for reason in report['reasons']:
        print(f"   {reason}")

# Trade cap (added Oct 18)
import json
from datetime import datetime, timezone
from pathlib import Path

def check_trade_cap(max_per_day=3):
    """Limit trades per day"""
    cap_file = Path.home() / "bot-a" / "logs" / "trade_cap.json"
    
    try:
        cap = json.loads(cap_file.read_text())
    except:
        cap = {"day": None, "count": 0}
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if cap["day"] != today:
        cap = {"day": today, "count": 0}
    
    if cap["count"] >= max_per_day:
        return False, f"Daily trade cap reached ({cap['count']}/{max_per_day})"
    
    cap["count"] += 1
    cap_file.write_text(json.dumps(cap))
    return True, f"Trade {cap['count']}/{max_per_day} today"
