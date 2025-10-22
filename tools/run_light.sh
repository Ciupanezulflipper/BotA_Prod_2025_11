#!/bin/bash
# Run Bot-A Light Runner
cd ~/bot-a/tools

PAIR=EURUSD
TF=M15
CONF_MIN=1.6
LOOP_SEC=60
THROTTLE=300

nohup env PAIR=$PAIR TF=$TF CONF_MIN=$CONF_MIN LOOP_SEC=$LOOP_SEC THROTTLE=$THROTTLE \
python3 runner_light.py >> ../logs/runner_light.log 2>&1 &
echo $! > ../logs/runner_light.pid
echo "Runner started (PID $(cat ../logs/runner_light.pid))"
