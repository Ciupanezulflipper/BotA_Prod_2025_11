#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/BotA/tools" || exit 1
RELAX_VOTE=1 DISABLE_INSIDE_DAY=1 USE_ADX=0 USE_BREAKOUT=0 \
PROVIDER_ORDER=${PROVIDER_ORDER:-twelvedata,alphavantage} \
python3 -m BotA.tools.final_runner --symbol EURUSD --send
