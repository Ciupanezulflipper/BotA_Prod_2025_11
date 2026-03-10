#!/usr/bin/env bash
export PYTHONPATH="$HOME/bot-a"

echo
echo "== Bot-A Quick Menu =="
echo "1) Analyze EURUSD (print)"
echo "2) Send EURUSD (combined card)"
echo "3) Analyze XAUUSD (print)"
echo "4) Send XAUUSD (combined card)"
echo "q) Quit"
read -rp "> " c

case "$c" in
  1) python "$HOME/bot-a/tools/final_signal.py" --symbol EURUSD ;;
  2) python "$HOME/bot-a/tools/final_signal.py" --symbol EURUSD --send ;;
  3) python "$HOME/bot-a/tools/final_signal.py" --symbol XAUUSD ;;
  4) python "$HOME/bot-a/tools/final_signal.py" --symbol XAUUSD --send ;;
  *) echo "bye";;
esac
