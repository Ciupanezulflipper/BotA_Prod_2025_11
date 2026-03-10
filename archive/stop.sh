#!/bin/bash
# Stop Bot-A Light Runner
cd ~/bot-a/tools

if [ -f ../logs/runner_light.pid ]; then
    kill -9 $(cat ../logs/runner_light.pid) 2>/dev/null
    rm -f ../logs/runner_light.pid
    echo "Runner stopped"
else
    echo "No PID file found"
fi
