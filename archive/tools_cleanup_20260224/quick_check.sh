#!/usr/bin/env bash
set -e
$HOME/BotA/tools/capctl.sh reset
$HOME/BotA/tools/logclean.sh rotate
$HOME/BotA/tools/envdiag.sh
cd $HOME/BotA && ./run_signal.sh
tail -n 80 $HOME/BotA/logs/cron.signals.log
