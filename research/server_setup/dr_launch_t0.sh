#!/usr/bin/env bash
# Launch the 2x2 T0 DETACHED (nohup) so it survives ssh/VPN drops; CSV is written incrementally.
# Usage: bash dr_launch_t0.sh [N] [model] [seed0] [workers]
nohup bash /research/d7/spc/yzyang4/scripts/dr_run_t0.sh "$@" \
  > /research/d7/spc/yzyang4/detectreplan/results/t0_run.log 2>&1 < /dev/null &
echo "T0_LAUNCHED pid=$! log=/research/d7/spc/yzyang4/detectreplan/results/t0_run.log"
