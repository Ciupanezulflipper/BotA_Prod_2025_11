#!/usr/bin/env python3
"""
MetaTrader 5 Connector for Trading Bot
Handles connection, orders, positions, and account info
"""

import MetaTrader5 as mt5
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import json

# Load environment
load_dotenv(Path.home() / "bot-a" / ".env.botA")

# MT5 Credentials
MT5_LOGIN = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
MT5_SERVER = os.getenv('MT5_SERVER', '')

class MT5Connector:
    """MetaTrader 5 connection and trading manager"""
    
    def __init__(self):
        self.connected = False
        self.account_info = None
    
    def connect(self) -> bool:
        """Initialize and connect to MT5"""
        try:
            # Initialize MT5
            if not mt5.initialize():
                print(f"❌ MT5 initialize failed: {mt5.last_error()}")
                return False
            
            # Login to account
            authorized = mt5.login(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER
            )
            
            if not authorized:
                print(f"❌ MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            # Get account info
            self.account_info = mt5.account_info()
            if self.account_info is None:
                print(f"❌ Failed to get account info: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            self.connected = True
            print(f"✅ Connected to MT5!")
            print(f"📊 Account: {self.account_info.login}")
            print(f"💰 Balance: ${self.account_info.balance:.2f}")
            print(f"🏦 Server: {self.account_info.server}")
            
            return True
            
        except Exception as e:
            print(f"❌ MT5 connection error: {e}")
            return False
    
    def disconnect(self):
        """Shutdown MT5 connection"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("✅ Disconnected from MT5")
    
    def get_account_info(self) -> dict:
        """Get current account information"""
        if not self.connected:
            return None
        
        info = mt5.account_info()
        if info is None:
            return None
        
        return {
            'login': info.login,
            'balance': info.balance,
            'equity': info.equity,
            'margin': info.margin,
            'margin_free': info.margin_free,
            'margin_level': info.margin_level,
            'profit': info.profit,
            'currency': info.currency,
            'leverage': info.leverage,
            'server': info.server
        }
    
    def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol information"""
        if not self.connected:
            return None
        
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"❌ Symbol {symbol} not found")
            return None
        
        return {
            'symbol': info.name,
            'bid': info.bid,
            'ask': info.ask,
            'spread': info.spread,
            'digits': info.digits,
            'point': info.point,
            'trade_contract_size': info.trade_contract_size,
            'volume_min': info.volume_min,
            'volume_max': info.volume_max,
            'volume_step': info.volume_step
        }
    
    def open_position(self, symbol: str, order_type: str, volume: float, 
                     sl: float = 0, tp: float = 0, comment: str = "") -> dict:
        """
        Open a trading position
        
        Args:
            symbol: Trading pair (e.g., "EURUSD")
            order_type: "BUY" or "SELL"
            volume: Lot size (e.g., 0.01)
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment
        
        Returns:
            dict with order result
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected'}
        
        # Prepare symbol
        if not symbol.endswith('.raw'):
            symbol = symbol + '.raw' if mt5.symbol_info(symbol + '.raw') else symbol
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {'success': False, 'error': f'Symbol {symbol} not found'}
        
        # Enable symbol
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                return {'success': False, 'error': f'Failed to select {symbol}'}
        
        # Determine order type
        order = mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = symbol_info.ask if order_type.upper() == "BUY" else symbol_info.bid
        
        # Prepare request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                'success': False,
                'error': f'Order failed: {result.retcode}',
                'comment': result.comment
            }
        
        return {
            'success': True,
            'ticket': result.order,
            'volume': result.volume,
            'price': result.price,
            'symbol': symbol,
            'type': order_type,
            'sl': sl,
            'tp': tp
        }
    
    def close_position(self, ticket: int) -> dict:
        """Close a position by ticket"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected'}
        
        # Get position
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {'success': False, 'error': f'Position {ticket} not found'}
        
        position = position[0]
        
        # Prepare close request
        order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Close by bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                'success': False,
                'error': f'Close failed: {result.retcode}',
                'comment': result.comment
            }
        
        return {
            'success': True,
            'ticket': ticket,
            'closed': True
        }
    
    def get_open_positions(self) -> list:
        """Get all open positions"""
        if not self.connected:
            return []
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        result = []
        for pos in positions:
            result.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'comment': pos.comment
            })
        
        return result


# Global instance
connector = MT5Connector()


def test_connection():
    """Test MT5 connection"""
    print("🧪 Testing MT5 Connection...")
    
    if connector.connect():
        print("\n✅ Connection successful!")
        
        # Get account info
        account = connector.get_account_info()
        if account:
            print(f"\n💰 Account Info:")
            print(f"   Balance: ${account['balance']:.2f}")
            print(f"   Equity: ${account['equity']:.2f}")
            print(f"   Margin Free: ${account['margin_free']:.2f}")
            print(f"   Leverage: 1:{account['leverage']}")
        
        # Test symbol info
        symbol_info = connector.get_symbol_info('EURUSD')
        if symbol_info:
            print(f"\n📊 EURUSD Info:")
            print(f"   Bid: {symbol_info['bid']:.5f}")
            print(f"   Ask: {symbol_info['ask']:.5f}")
            print(f"   Spread: {symbol_info['spread']}")
        
        connector.disconnect()
        return True
    else:
        print("\n❌ Connection failed!")
        return False


if __name__ == "__main__":
    test_connection()
