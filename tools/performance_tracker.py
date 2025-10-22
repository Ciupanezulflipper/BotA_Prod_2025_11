#!/usr/bin/env python3
"""
Performance Tracker for Trading Bot
Tracks wins, losses, profit/loss, and generates statistics
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# Configuration
BOT_DIR = Path.home() / "bot-a"
DATA_DIR = BOT_DIR / "data"
PERF_FILE = DATA_DIR / "performance.json"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)


class PerformanceTracker:
    """Track and analyze trading performance"""
    
    def __init__(self):
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load performance data from file"""
        if PERF_FILE.exists():
            try:
                return json.loads(PERF_FILE.read_text())
            except:
                return self._init_data()
        return self._init_data()
    
    def _init_data(self) -> Dict:
        """Initialize empty performance data"""
        return {
            "trades": [],
            "daily_stats": {},
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "best_trade": None,
            "worst_trade": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _save_data(self):
        """Save performance data to file"""
        PERF_FILE.write_text(json.dumps(self.data, indent=2))
    
    def add_trade(self, trade: Dict):
        """
        Add a completed trade to performance history
        
        Args:
            trade: {
                'pair': 'EURUSD',
                'action': 'BUY' or 'SELL',
                'entry': 1.0850,
                'exit': 1.0900,
                'sl': 1.0830,
                'tp': 1.0900,
                'result': 'WIN' or 'LOSS',
                'profit_pips': 50.0,
                'profit_usd': 50.0,
                'size': 0.01,
                'opened_at': '2025-10-19T12:00:00Z',
                'closed_at': '2025-10-19T14:00:00Z',
                'duration_hours': 2.0,
                'signal_score': 2.5
            }
        """
        # Add timestamp if not present
        if 'closed_at' not in trade:
            trade['closed_at'] = datetime.now(timezone.utc).isoformat()
        
        # Add to trades list
        self.data['trades'].append(trade)
        
        # Update totals
        self.data['total_trades'] += 1
        
        if trade['result'] == 'WIN':
            self.data['winning_trades'] += 1
            self.data['total_profit'] += trade.get('profit_usd', 0)
        else:
            self.data['losing_trades'] += 1
            self.data['total_loss'] += abs(trade.get('profit_usd', 0))
        
        # Update best/worst
        if self.data['best_trade'] is None or trade.get('profit_usd', 0) > self.data['best_trade'].get('profit_usd', 0):
            self.data['best_trade'] = trade
        
        if self.data['worst_trade'] is None or trade.get('profit_usd', 0) < self.data['worst_trade'].get('profit_usd', 0):
            self.data['worst_trade'] = trade
        
        # Update daily stats
        trade_date = trade['closed_at'][:10]  # YYYY-MM-DD
        if trade_date not in self.data['daily_stats']:
            self.data['daily_stats'][trade_date] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'profit': 0.0
            }
        
        day_stats = self.data['daily_stats'][trade_date]
        day_stats['trades'] += 1
        if trade['result'] == 'WIN':
            day_stats['wins'] += 1
        else:
            day_stats['losses'] += 1
        day_stats['profit'] += trade.get('profit_usd', 0)
        
        # Save
        self._save_data()
    
    def get_summary(self) -> Dict:
        """Get performance summary"""
        total = self.data['total_trades']
        wins = self.data['winning_trades']
        losses = self.data['losing_trades']
        
        win_rate = (wins / total * 100) if total > 0 else 0
        net_profit = self.data['total_profit'] - self.data['total_loss']
        avg_win = self.data['total_profit'] / wins if wins > 0 else 0
        avg_loss = self.data['total_loss'] / losses if losses > 0 else 0
        profit_factor = self.data['total_profit'] / self.data['total_loss'] if self.data['total_loss'] > 0 else 0
        
        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': losses,
            'win_rate': win_rate,
            'total_profit': self.data['total_profit'],
            'total_loss': self.data['total_loss'],
            'net_profit': net_profit,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': self.data['best_trade'],
            'worst_trade': self.data['worst_trade']
        }
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        return self.data['trades'][-limit:]
    
    def get_daily_stats(self, days: int = 7) -> Dict:
        """Get stats for last N days"""
        today = datetime.now(timezone.utc).date()
        stats = {}
        
        for i in range(days):
            date = (today - timedelta(days=i)).isoformat()
            stats[date] = self.data['daily_stats'].get(date, {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'profit': 0.0
            })
        
        return stats
    
    def get_weekly_summary(self) -> Dict:
        """Get current week summary"""
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=today.weekday())
        
        week_trades = 0
        week_wins = 0
        week_losses = 0
        week_profit = 0.0
        
        for i in range(7):
            date = (week_start + timedelta(days=i)).isoformat()
            if date in self.data['daily_stats']:
                day = self.data['daily_stats'][date]
                week_trades += day['trades']
                week_wins += day['wins']
                week_losses += day['losses']
                week_profit += day['profit']
        
        return {
            'trades': week_trades,
            'wins': week_wins,
            'losses': week_losses,
            'profit': week_profit,
            'win_rate': (week_wins / week_trades * 100) if week_trades > 0 else 0
        }
    
    def get_monthly_summary(self) -> Dict:
        """Get current month summary"""
        today = datetime.now(timezone.utc)
        month_prefix = today.strftime('%Y-%m')
        
        month_trades = 0
        month_wins = 0
        month_losses = 0
        month_profit = 0.0
        
        for date, stats in self.data['daily_stats'].items():
            if date.startswith(month_prefix):
                month_trades += stats['trades']
                month_wins += stats['wins']
                month_losses += stats['losses']
                month_profit += stats['profit']
        
        return {
            'trades': month_trades,
            'wins': month_wins,
            'losses': month_losses,
            'profit': month_profit,
            'win_rate': (month_wins / month_trades * 100) if month_trades > 0 else 0
        }
    
    def format_summary_text(self) -> str:
        """Format summary as text for Telegram"""
        summary = self.get_summary()
        
        text = f"""
📊 **PERFORMANCE SUMMARY**

**Overall Stats:**
• Total Trades: {summary['total_trades']}
• Win Rate: {summary['win_rate']:.1f}%
• Wins: {summary['winning_trades']} | Losses: {summary['losing_trades']}

**Profit/Loss:**
• Total Profit: ${summary['total_profit']:.2f}
• Total Loss: ${summary['total_loss']:.2f}
• Net P/L: ${summary['net_profit']:.2f}
• Avg Win: ${summary['avg_win']:.2f}
• Avg Loss: ${summary['avg_loss']:.2f}
• Profit Factor: {summary['profit_factor']:.2f}

**Best Trade:**
"""
        
        if summary['best_trade']:
            best = summary['best_trade']
            text += f"• {best['pair']} {best['action']}: +${best.get('profit_usd', 0):.2f}\n"
        else:
            text += "• No trades yet\n"
        
        text += "\n**Worst Trade:**\n"
        if summary['worst_trade']:
            worst = summary['worst_trade']
            text += f"• {worst['pair']} {worst['action']}: ${worst.get('profit_usd', 0):.2f}\n"
        else:
            text += "• No trades yet\n"
        
        return text
    
    def format_weekly_text(self) -> str:
        """Format weekly summary as text"""
        week = self.get_weekly_summary()
        
        return f"""
📅 **THIS WEEK**

• Trades: {week['trades']}
• Wins: {week['wins']} | Losses: {week['losses']}
• Win Rate: {week['win_rate']:.1f}%
• Net P/L: ${week['profit']:.2f}
"""
    
    def format_monthly_text(self) -> str:
        """Format monthly summary as text"""
        month = self.get_monthly_summary()
        
        return f"""
📆 **THIS MONTH**

• Trades: {month['trades']}
• Wins: {month['wins']} | Losses: {month['losses']}
• Win Rate: {month['win_rate']:.1f}%
• Net P/L: ${month['profit']:.2f}
"""


# Global instance
tracker = PerformanceTracker()


def add_trade(trade: Dict):
    """Add a trade to performance tracking"""
    tracker.add_trade(trade)


def get_summary() -> Dict:
    """Get performance summary"""
    return tracker.get_summary()


def get_summary_text() -> str:
    """Get formatted summary text"""
    return tracker.format_summary_text()


def get_weekly_text() -> str:
    """Get weekly summary text"""
    return tracker.format_weekly_text()


def get_monthly_text() -> str:
    """Get monthly summary text"""
    return tracker.format_monthly_text()


if __name__ == "__main__":
    # Test with sample trades
    print("📊 Testing Performance Tracker...")
    
    # Add sample winning trade
    tracker.add_trade({
        'pair': 'EURUSD',
        'action': 'BUY',
        'entry': 1.0850,
        'exit': 1.0900,
        'sl': 1.0830,
        'tp': 1.0900,
        'result': 'WIN',
        'profit_pips': 50.0,
        'profit_usd': 50.0,
        'size': 0.01,
        'signal_score': 2.5
    })
    
    # Add sample losing trade
    tracker.add_trade({
        'pair': 'GBPUSD',
        'action': 'SELL',
        'entry': 1.2650,
        'exit': 1.2630,
        'sl': 1.2670,
        'tp': 1.2600,
        'result': 'LOSS',
        'profit_pips': -20.0,
        'profit_usd': -20.0,
        'size': 0.01,
        'signal_score': 2.0
    })
    
    print(tracker.format_summary_text())
    print(tracker.format_weekly_text())
    print(tracker.format_monthly_text())
    
    print("\n✅ Performance tracker working!")
