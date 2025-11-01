BotA — status_pretty v2.0 (Merged from Grok, Gemini, Perplexity, Claude)

What this is
- A pure formatter module that renders Telegram-safe outputs:
  Sections = Header → Signal → Metrics → Health
  Modes    = basic (2 lines/pair) | advanced (4–5 lines/pair)
- No changes to your proven pipeline; safe to add now and integrate later.

Quick demo
  python3 -m py_compile $HOME/BotA/tools/status_pretty.py && echo "✅ Syntax OK"
  python3 $HOME/BotA/tools/status_pretty.py | sed -n '1,40p'
  python3 $HOME/BotA/tools/status_pretty_demo.py | sed -n '1,80p'

Planned integration (later, non-breaking)
- tele_control.py:
    /status            -> use status_pretty.format_status(..., mode="basic")
    /status advanced   -> same with mode="advanced"
- analyze_now.py:
    pretty preview block uses advanced mode for selected pairs

Design decisions (cross-audit consensus)
- Keep Telegram messages < 3500 chars; hard cut at 4000 with safe truncation.
- Core metrics in message: RSI, EMA(9/21) trend arrow, Vote, Freshness.
- Health line shows freshness; Provider/Cache only if helpful; errors are surfaced.
- ADX/ATR/Sentiment only in advanced mode if available; otherwise hidden.
- Emojis are functional anchors (📊, 🟢/🔴/⚪, 📈, 🩺); minimal to avoid clutter.
