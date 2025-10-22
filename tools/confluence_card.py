#!/data/data/com.termux/files/usr/bin/python3
"""
Confluence Card Formatter
Generates Telegram-friendly signal cards
"""

from datetime import datetime, timezone

def generate_confluence_card(data):
    pair = data.get("pair", "EURUSD")
    confidence = data.get("confidence", 0)
    sentiment = data.get("sentiment", "NEUTRAL")
    sentiment_score = data.get("sentiment_score", 0)
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    analysis = data.get("analysis", {})
    signals = analysis.get("technical_signals", {})

    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        tstr = dt.strftime("%H:%M UTC")
        dstr = dt.strftime("%Y-%m-%d")
    except:
        tstr, dstr = "Unknown", "Unknown"

    # Emojis
    conf_emoji = "🔥" if confidence >= 8 else "⚡" if confidence >= 6 else "📈" if confidence >= 4 else "📊"
    sent_emoji = "🟢" if "BUY" in sentiment.upper() else "🔴" if "SELL" in sentiment.upper() else "⚪"

    # Technical summary
    lines = []
    for tf, sig in signals.items():
        e = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
        lines.append(f"• {tf}: {e} {sig}")
    summary = "\n".join(lines) if lines else "• No signals"

    # Build message
    msg = f"""📊 <b>{pair} Multi-TF Signal</b>

{sent_emoji} Sentiment: <b>{sentiment}</b>
{conf_emoji} Confidence: <b>{confidence}/10</b> ({sentiment_score}/6 sentiment)

📈 <b>Timeframes</b>
{summary}

🕒 {tstr} | {dstr}
<i>Auto-generated confluence scan</i>"""

    return msg

# Test run
if __name__ == "__main__":
    sample = {
        "pair": "EURUSD",
        "confidence": 7.2,
        "sentiment": "strong SELL",
        "sentiment_score": 6,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {
            "technical_signals": {
                "M5": "SELL", "M15": "SELL", "H1": "NEUTRAL", "H4": "BUY", "D1": "SELL"
            }
        }
    }
    print(generate_confluence_card(sample))
