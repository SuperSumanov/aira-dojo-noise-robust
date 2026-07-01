#!/usr/bin/env bash
# Run-B: 12x12, swap, long post-horizon (t_c early) — tests inference-from-experience + replanning on
# a bigger grid. Detached + incremental CSV (t0_2x2_B12swap.csv). Usage: bash dr_launch_B.sh N model seed0 workers
source ~/env_setup.sh 2>/dev/null
source /research/d7/spc/yzyang4/detectreplan/.env
export DR_SIZE=12 DR_MINDIST=10 DR_SHIFT=swap DR_TCFRAC=0.25 DR_TAG=B12swap
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/detectreplan || exit 1
nohup "$PY" run_t0.py "$@" > results/t0_run_B12swap.log 2>&1 < /dev/null &
echo "B_LAUNCHED pid=$! tag=B12swap log=results/t0_run_B12swap.log"
