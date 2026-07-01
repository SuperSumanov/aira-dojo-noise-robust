#!/usr/bin/env bash
# Poll until all mcts_t0 sbatch jobs finish, then pool the T0 signals across seeds.
source ~/env_setup.sh
echo "waiting for mcts_t0 jobs..."
for i in $(seq 1 120); do
  n=$(squeue -u yzyang4 -h -n mcts_t0 2>/dev/null | wc -l)
  echo "[$(date -u +%H:%M:%S)] mcts_t0 jobs remaining: $n"
  [ "$n" -eq 0 ] && break
  sleep 90
done
echo "=== all mcts_t0 jobs done; pooling T0 signals ==="
bash /research/d7/spc/yzyang4/scripts/pool_t0_r2.sh
echo "WAIT_AND_POOL_DONE"
