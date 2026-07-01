#!/usr/bin/env bash
# Wait up to ~3 min for the daemon to refill the queue (after the projgpu8 fix freed 2 slots).
source ~/env_setup.sh
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_matrix_submitted.txt
for i in $(seq 1 15); do
  q=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
  n=$(wc -l < "$STATE" 2>/dev/null)
  if [ "$q" -ge 4 ]; then
    echo "REFILLED: queue=$q submitted=$n/30"
    squeue -u yzyang4
    echo "--- daemon log ---"; tail -n 4 /research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log
    echo "REFILL_OK"; exit 0
  fi
  sleep 12
done
echo "NO REFILL after ~180s: queue=$q submitted=$n/30"
squeue -u yzyang4
echo "--- daemon log ---"; tail -n 5 /research/d7/spc/yzyang4/aira-dojo-runs/matrix_daemon.log
echo "REFILL_PENDING"
