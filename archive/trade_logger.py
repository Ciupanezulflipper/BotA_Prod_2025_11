#!/usr/bin/env python3
"""
Manual Trade Logger
Allows logging trades via Telegram for performance tracking
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from tools.performance_tracker import add_trade

# Bot directory
BOT_DIR = Path.home() / "bot-a"
DATA_DIR = BOT_DIR / "data"

# Temporary storage for ongoing trade logging
TEMP_FILE = DATA_DIR / "temp_trade.json"


class TradeLogger:
    """Helper for logging manual trades"""
    
    def __init__(self):
        self.temp_trade = {}
    
    def start_log(self, user_id: int):
        """Start a new trade log"""
        self.temp_trade = {
            'user_id': user_id,
            'step': 'pair',
            'data': {}
        }
        self._save_temp()
        return "📝 **Log New Trade**\n\nWhat pair did you trade?\n\nExamples: EURUSD, GBPUSD, USDJPY"
    
    def process_input(self, user_id: int, text: str) -> dict:
        """
        Process user input step by step
        Returns: {'done': bool, 'message': str, 'buttons': list}
        """
        self._load_temp()
        
        if not self.temp_trade or self.temp_trade.get('user_id') != user_id:
            return {
                'done': False,
                'message': "No active trade log. Use /log_trade to start.",
                'buttons': []
            }
        
        step = self.temp_trade['step']
        data = self.temp_trade['data']
        
        # Step 1: Pair
        if step == 'pair':
            pair = text.upper().replace('/', '')
            data['pair'] = pair
            self.temp_trade['step'] = 'action'
            self._save_temp()
            return {
                'done': False,
                'message': f"✅ Pair: {pair}\n\nBUY or SELL?",
                'buttons': [
                    [('BUY 📈', 'trade_log_BUY'), ('SELL 📉', 'trade_log_SELL')]
                ]
            }
        
        # Step 2: Action (BUY/SELL)
        elif step == 'action':
            action = text.upper()
            if action not in ['BUY', 'SELL']:
                return {
                    'done': False,
                    'message': "Please choose BUY or SELL",
                    'buttons': [
                        [('BUY 📈', 'trade_log_BUY'), ('SELL 📉', 'trade_log_SELL')]
                    ]
                }
            data['action'] = action
            self.temp_trade['step'] = 'entry'
            self._save_temp()
            return {
                'done': False,
                'message': f"✅ Action: {action}\n\nWhat was your ENTRY price?\n\nExample: 1.0850",
                'buttons': []
            }
        
        # Step 3: Entry price
        elif step == 'entry':
            try:
                entry = float(text)
                data['entry'] = entry
                self.temp_trade['step'] = 'exit'
                self._save_temp()
                return {
                    'done': False,
                    'message': f"✅ Entry: {entry}\n\nWhat was your EXIT price?\n\nExample: 1.0900",
                    'buttons': []
                }
            except:
                return {
                    'done': False,
                    'message': "Please enter a valid price (e.g., 1.0850)",
                    'buttons': []
                }
        
        # Step 4: Exit price
        elif step == 'exit':
            try:
                exit_price = float(text)
                data['exit'] = exit_price
                self.temp_trade['step'] = 'size'
                self._save_temp()
                return {
                    'done': False,
                    'message': f"✅ Exit: {exit_price}\n\nWhat was your position size (lots)?\n\nExample: 0.01",
                    'buttons': [
                        [('0.01', 'trade_log_0.01'), ('0.05', 'trade_log_0.05'), ('0.10', 'trade_log_0.10')]
                    ]
                }
            except:
                return {
                    'done': False,
                    'message': "Please enter a valid price (e.g., 1.0900)",
                    'buttons': []
                }
        
        # Step 5: Position size
        elif step == 'size':
            try:
                size = float(text)
                data['size'] = size
                
                # Calculate profit/loss
                pair = data['pair']
                entry = data['entry']
                exit_price = data['exit']
                action = data['action']
                
                # Calculate pips
                if action == 'BUY':
                    pips = (exit_price - entry) * 10000
                else:
                    pips = (entry - exit_price) * 10000
                
                # Calculate USD (approximate, assuming $10/pip for 0.01 lot)
                profit_usd = pips * (size / 0.01)
                
                result = 'WIN' if profit_usd > 0 else 'LOSS'
                
                data['profit_pips'] = round(pips, 1)
                data['profit_usd'] = round(profit_usd, 2)
                data['result'] = result
                
                # Save to performance tracker
                trade_data = {
                    'pair': pair,
                    'action': action,
                    'entry': entry,
                    'exit': exit_price,
                    'size': size,
                    'result': result,
                    'profit_pips': data['profit_pips'],
                    'profit_usd': data['profit_usd'],
                    'opened_at': datetime.now(timezone.utc).isoformat(),
                    'closed_at': datetime.now(timezone.utc).isoformat(),
                    'comment': 'Manual trade via logger'
                }
                
                add_trade(trade_data)
                
                # Clear temp
                self._clear_temp()
                
                emoji = "🎉" if result == 'WIN' else "😔"
                sign = "+" if profit_usd > 0 else ""
                
                message = f"""
{emoji} **TRADE LOGGED!**

**Trade Details:**
• Pair: {pair}
• Action: {action}
• Entry: {entry}
• Exit: {exit_price}
• Size: {size} lots

**Result:**
• Pips: {sign}{data['profit_pips']}
• P/L: {sign}${data['profit_usd']}
• Result: {result}

✅ Added to performance tracker!

Use /performance to see updated stats!
"""
                
                return {
                    'done': True,
                    'message': message,
                    'buttons': []
                }
                
            except Exception as e:
                return {
                    'done': False,
                    'message': f"Error: {e}\nPlease enter a valid size (e.g., 0.01)",
                    'buttons': []
                }
    
    def _save_temp(self):
        """Save temporary trade data"""
        TEMP_FILE.write_text(json.dumps(self.temp_trade, indent=2))
    
    def _load_temp(self):
        """Load temporary trade data"""
        if TEMP_FILE.exists():
            try:
                self.temp_trade = json.loads(TEMP_FILE.read_text())
            except:
                self.temp_trade = {}
    
    def _clear_temp(self):
        """Clear temporary trade data"""
        self.temp_trade = {}
        if TEMP_FILE.exists():
            TEMP_FILE.unlink()
    
    def cancel_log(self, user_id: int):
        """Cancel current trade log"""
        self._clear_temp()
        return "❌ Trade log cancelled."


# Global instance
logger = TradeLogger()


if __name__ == "__main__":
    print("🧪 Trade Logger Test")
    print("\nThis module is used by the Telegram menu bot.")
    print("Use /log_trade in Telegram to start logging trades!")
