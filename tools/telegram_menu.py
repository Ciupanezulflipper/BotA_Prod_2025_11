#!/usr/bin/env python3
"""
Telegram Interactive Menu for Bot Control
Provides: Mode toggle, status, settings, emergency stop, performance tracking, trade logging
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment
load_dotenv(Path.home() / "bot-a" / ".env.botA")

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Import performance tracker
try:
    from tools.performance_tracker import get_summary_text, get_weekly_text, get_monthly_text
    PERFORMANCE_AVAILABLE = True
except ImportError:
    PERFORMANCE_AVAILABLE = False
    print("⚠️ Performance tracker not available")

# Import trade logger
try:
    from tools.trade_logger import logger
    TRADE_LOGGER_AVAILABLE = True
except ImportError:
    TRADE_LOGGER_AVAILABLE = False
    print("⚠️ Trade logger not available")


# === CONFIGURATION ===
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
BOT_DIR = Path.home() / "bot-a"
DATA_DIR = BOT_DIR / "data"
LOGS_DIR = BOT_DIR / "logs"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Track if user is in trade logging mode
user_logging_mode = {}


# === TRADING MODE MANAGEMENT ===

def get_trading_mode() -> dict:
    """Get current trading mode (auto/manual)"""
    mode_file = DATA_DIR / "trading_mode.json"
    
    try:
        if mode_file.exists():
            return json.loads(mode_file.read_text())
        else:
            default_mode = {
                "mode": "manual",
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "changed_by": "system_default"
            }
            mode_file.write_text(json.dumps(default_mode, indent=2))
            return default_mode
    except Exception as e:
        print(f"❌ Error reading mode: {e}")
        return {"mode": "manual", "changed_at": "unknown", "changed_by": "error"}


def set_trading_mode(mode: str, changed_by: str = "telegram") -> bool:
    """Set trading mode (auto/manual)"""
    mode_file = DATA_DIR / "trading_mode.json"
    
    if mode not in ["auto", "manual"]:
        return False
    
    try:
        data = {
            "mode": mode,
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": changed_by
        }
        mode_file.write_text(json.dumps(data, indent=2))
        print(f"✅ Trading mode set to: {mode}")
        return True
    except Exception as e:
        print(f"❌ Error setting mode: {e}")
        return False


def get_bot_status() -> dict:
    """Get comprehensive bot status"""
    
    # Get trade cap
    trade_cap_file = LOGS_DIR / "trade_cap.json"
    try:
        trade_cap = json.loads(trade_cap_file.read_text())
    except:
        trade_cap = {"day": "unknown", "count": 0}
    
    # Get last log entry
    log_file = LOGS_DIR / "auto_h1.log"
    last_run = "Unknown"
    last_signal = "No signals yet"
    
    try:
        if log_file.exists():
            lines = log_file.read_text().splitlines()
            for line in reversed(lines):
                if "✓ run ok" in line or "✗ run failed" in line:
                    last_run = line.split("]")[0].replace("[", "").strip()
                    break
            
            for line in reversed(lines):
                if "📊 EURUSD" in line:
                    idx = lines.index(line)
                    last_signal = "\n".join(lines[idx:min(idx+5, len(lines))])
                    break
    except Exception as e:
        print(f"⚠️ Error reading logs: {e}")
    
    # Check if bot is running
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-f", "auto_h1.sh"],
            capture_output=True,
            text=True
        )
        bot_running = bool(result.stdout.strip())
    except:
        bot_running = False
    
    return {
        "mode": get_trading_mode()["mode"],
        "running": bot_running,
        "trade_cap": trade_cap,
        "last_run": last_run,
        "last_signal": last_signal
    }


# === TELEGRAM COMMAND HANDLERS ===

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show main menu"""
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display main control panel"""
    
    status = get_bot_status()
    mode = status["mode"]
    running = status["running"]
    trade_count = status["trade_cap"]["count"]
    trade_day = status["trade_cap"]["day"]
    
    mode_emoji = "🤖" if mode == "auto" else "👤"
    running_emoji = "✅" if running else "❌"
    
    message = f"""
🎛️ **BOT CONTROL PANEL**

**Status:**
{running_emoji} Bot: {'Running' if running else 'Stopped'}
{mode_emoji} Mode: **{mode.upper()}**
📊 Trades Today: {trade_count}/3 ({trade_day})

**Quick Actions:**
"""
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'👤 Switch to Manual' if mode == 'auto' else '🤖 Switch to Auto'}", 
                callback_data='toggle_mode'
            )
        ],
        [
            InlineKeyboardButton("📊 Full Status", callback_data='full_status'),
            InlineKeyboardButton("📈 Last Signal", callback_data='last_signal')
        ],
        [
            InlineKeyboardButton("📉 Performance", callback_data='performance'),
            InlineKeyboardButton("📝 Log Trade", callback_data='log_trade')
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data='settings'),
            InlineKeyboardButton("📋 Help", callback_data='help')
        ],
        [
            InlineKeyboardButton("🛑 Emergency Stop", callback_data='emergency_stop')
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data='refresh')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == 'toggle_mode':
        await toggle_mode_handler(update, context)
    elif action == 'full_status':
        await full_status_handler(update, context)
    elif action == 'last_signal':
        await last_signal_handler(update, context)
    elif action == 'performance':
        await performance_handler(update, context)
    elif action == 'performance_week':
        await performance_week_handler(update, context)
    elif action == 'performance_month':
        await performance_month_handler(update, context)
    elif action == 'log_trade':
        await log_trade_handler(update, context)
    elif action.startswith('trade_log_'):
        await trade_log_input_handler(update, context, action)
    elif action == 'settings':
        await settings_handler(update, context)
    elif action == 'help':
        await help_handler(update, context)
    elif action == 'emergency_stop':
        await emergency_stop_handler(update, context)
    elif action == 'refresh':
        await show_main_menu(update, context)
    elif action == 'back_to_menu':
        await show_main_menu(update, context)


async def toggle_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle between auto and manual mode"""
    current_mode = get_trading_mode()["mode"]
    new_mode = "manual" if current_mode == "auto" else "auto"
    
    if set_trading_mode(new_mode, "telegram_menu"):
        emoji = "🤖" if new_mode == "auto" else "👤"
        message = f"""
{emoji} **Mode Changed!**

**New Mode:** {new_mode.upper()}

{'⚡ Bot will now trade automatically based on signals.' if new_mode == 'auto' else '📱 Bot will send signals but you control trades manually.'}

**Changed:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
"""
        
        keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.edit_message_text("❌ Failed to change mode!")


async def full_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed bot status"""
    status = get_bot_status()
    
    message = f"""
📊 **FULL BOT STATUS**

**System:**
• Bot Process: {'✅ Running' if status['running'] else '❌ Stopped'}
• Trading Mode: {'🤖 AUTO' if status['mode'] == 'auto' else '👤 MANUAL'}

**Trading:**
• Trades Today: {status['trade_cap']['count']}/3
• Trade Cap Day: {status['trade_cap']['day']}
• Last Run: {status['last_run']}

**Performance:**
• Queue Pending: {len(list((BOT_DIR / 'queue' / 'pending').glob('*.json')))} signals
• Queue Sent: {len(list((BOT_DIR / 'queue' / 'sent').glob('*.json')))} signals

**Environment:**
• Python: ✅ Available
• Termux: ✅ Running
• Telegram: ✅ Connected
"""
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def last_signal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last trading signal"""
    status = get_bot_status()
    
    message = f"""
📈 **LAST SIGNAL**

{status['last_signal']}

**Tip:** Check logs for more details:
`tail -50 ~/bot-a/logs/auto_h1.log`
"""
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def performance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show performance summary with options"""
    
    if not PERFORMANCE_AVAILABLE:
        message = "📉 **Performance Tracking**\n\nPerformance tracker not yet initialized.\nIt will start tracking once you have completed trades."
    else:
        message = get_summary_text()
    
    keyboard = [
        [
            InlineKeyboardButton("📅 This Week", callback_data='performance_week'),
            InlineKeyboardButton("📆 This Month", callback_data='performance_month')
        ],
        [InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def performance_week_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show weekly performance"""
    
    if not PERFORMANCE_AVAILABLE:
        message = "📉 Performance tracking not available yet."
    else:
        message = get_summary_text() + "\n" + get_weekly_text()
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Full Summary", callback_data='performance'),
            InlineKeyboardButton("📆 This Month", callback_data='performance_month')
        ],
        [InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def performance_month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly performance"""
    
    if not PERFORMANCE_AVAILABLE:
        message = "📉 Performance tracking not available yet."
    else:
        message = get_summary_text() + "\n" + get_monthly_text()
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Full Summary", callback_data='performance'),
            InlineKeyboardButton("📅 This Week", callback_data='performance_week')
        ],
        [InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def log_trade_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start trade logging process"""
    if not TRADE_LOGGER_AVAILABLE:
        message = "📝 Trade logger not available"
        keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    else:
        user_id = update.callback_query.from_user.id
        user_logging_mode[user_id] = True
        message = logger.start_log(user_id)
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def trade_log_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Handle button inputs during trade logging"""
    user_id = update.callback_query.from_user.id
    
    # Extract value from action (e.g., 'trade_log_BUY' -> 'BUY')
    value = action.replace('trade_log_', '')
    
    result = logger.process_input(user_id, value)
    
    if result['buttons']:
        keyboard = result['buttons'] + [[InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')]]
    else:
        if result['done']:
            keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
            user_logging_mode[user_id] = False
        else:
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        result['message'],
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during trade logging"""
    user_id = update.message.from_user.id
    
    if user_id in user_logging_mode and user_logging_mode[user_id]:
        text = update.message.text
        result = logger.process_input(user_id, text)
        
        if result['buttons']:
            keyboard_buttons = []
            for row in result['buttons']:
                button_row = []
                for btn in row:
                    button_row.append(InlineKeyboardButton(btn[0], callback_data=btn[1]))
                keyboard_buttons.append(button_row)
            keyboard_buttons.append([InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')])
            reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        else:
            if result['done']:
                keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
                user_logging_mode[user_id] = False
            else:
                keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            result['message'],
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings menu"""
    message = """
⚙️ **SETTINGS**

**Current Configuration:**
• Max Daily Trades: 3
• Risk Per Trade: 2%
• Min Signal Score: 2.0
• Trading Pairs: EURUSD

**Coming Soon:**
• Adjust risk settings
• Add/remove pairs
• Change trade limits
• Notification preferences
"""
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    message = """
📋 **HELP & COMMANDS**

**Available Commands:**
• `/start` - Show main menu
• `/status` - Quick status check
• `/mode` - Toggle auto/manual
• `/stop` - Emergency stop
• `/log_trade` - Log a manual trade

**Trading Modes:**
• 🤖 **AUTO** - Bot trades automatically
• 👤 **MANUAL** - Bot sends signals only

**Manual Trading:**
• Receive signal from bot
• Execute trade in XTB app
• Use "Log Trade" to record it
• Performance tracker updates automatically

**Safety Features:**
• Max 3 trades per day
• 2% risk per trade
• Stop loss on every trade
• Emergency stop button

**Need Help?**
Contact: tomagm2010@gmail.com
"""
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def emergency_stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emergency stop - disable auto-trading"""
    
    set_trading_mode("manual", "emergency_stop")
    
    message = """
🛑 **EMERGENCY STOP ACTIVATED**

**Actions Taken:**
✅ Switched to MANUAL mode
✅ Auto-trading DISABLED
✅ No new trades will be opened

**Current Positions:**
⚠️ Any open positions remain active
⚠️ Stop losses remain in place

**To Resume:**
Tap "Switch to Auto" when ready

**Stopped:** """ + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick status check via /status command"""
    status = get_bot_status()
    
    message = f"""
📊 **QUICK STATUS**

Bot: {'✅ Running' if status['running'] else '❌ Stopped'}
Mode: {'🤖 AUTO' if status['mode'] == 'auto' else '👤 MANUAL'}
Trades: {status['trade_cap']['count']}/3 today

Last run: {status['last_run']}

Type /start for full menu
"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle mode via /mode command"""
    current_mode = get_trading_mode()["mode"]
    new_mode = "manual" if current_mode == "auto" else "auto"
    
    if set_trading_mode(new_mode, "command"):
        emoji = "🤖" if new_mode == "auto" else "👤"
        await update.message.reply_text(
            f"{emoji} Mode changed to: **{new_mode.upper()}**",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to change mode!")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emergency stop via /stop command"""
    set_trading_mode("manual", "stop_command")
    await update.message.reply_text(
        "🛑 **EMERGENCY STOP**\n\nAuto-trading disabled!\n\nType /start to access menu",
        parse_mode='Markdown'
    )


async def log_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start trade logging via /log_trade command"""
    if not TRADE_LOGGER_AVAILABLE:
        await update.message.reply_text("📝 Trade logger not available")
        return
    
    user_id = update.message.from_user.id
    user_logging_mode[user_id] = True
    message = logger.start_log(user_id)
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


def main():
    """Start the Telegram bot menu"""
    
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env.botA!")
        sys.exit(1)
    
    print("🚀 Starting Telegram Menu Bot...")
    print(f"📱 Bot Token: {BOT_TOKEN[:20]}...")
    print(f"👤 Chat ID: {CHAT_ID}")
    
    # Create application WITHOUT job queue
    application = Application.builder().token(BOT_TOKEN).job_queue(None).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("log_trade", log_trade_command))
    
    # Add callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add text message handler for trade logging
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    print("✅ Telegram Menu Bot Started!")
    print("📱 Send /start to your bot to see the menu")
    print("📉 Performance tracking enabled!")
    print("📝 Trade logging enabled!")
    print("🛑 Press Ctrl+C to stop")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
