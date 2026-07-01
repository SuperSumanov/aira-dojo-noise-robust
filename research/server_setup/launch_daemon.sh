#!/usr/bin/env bash
# Launch the T1 matrix submitter daemon detached (survives ssh disconnect / Claude close).
nohup bash /research/d7/spc/yzyang4/scripts/submit_daemon.sh \
  > /research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log 2>&1 < /dev/null &
echo "DAEMON_LAUNCHED pid=$! log=/research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log"
