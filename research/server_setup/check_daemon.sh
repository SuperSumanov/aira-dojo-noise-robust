#!/usr/bin/env bash
source ~/env_setup.sh
echo "=== daemon process (pid 2894538) ==="
ps -p 2894538 -o pid,etimes,cmd 2>/dev/null || echo "DAEMON NOT RUNNING"
echo "=== queue ==="
squeue -u yzyang4
echo "=== daemon log tail ==="
tail -n 5 /research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log
echo CHECK_DAEMON_DONE
