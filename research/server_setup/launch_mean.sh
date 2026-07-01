#!/usr/bin/env bash
# Launch the lambda=0 mean-arm submitter detached.
nohup bash /research/d7/spc/yzyang4/scripts/submit_mean_daemon.sh \
  > /research/d7/spc/yzyang4/aira-dojo-runs/mean_daemon.log 2>&1 < /dev/null &
echo "MEAN_DAEMON_LAUNCHED pid=$! log=/research/d7/spc/yzyang4/aira-dojo-runs/mean_daemon.log"
