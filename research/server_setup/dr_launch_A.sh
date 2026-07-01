#!/usr/bin/env bash
# Run-A: 12x12, rotate (90deg-clockwise rule, harder to apply) — tests whether replanning given the
# rule costs anything (does c1r1 regret rise above 0?). Detached + incremental (t0_2x2_A12rot.csv).
source ~/env_setup.sh 2>/dev/null
source /research/d7/spc/yzyang4/detectreplan/.env
export DR_SIZE=12 DR_MINDIST=10 DR_SHIFT=rotate DR_TCFRAC=0.5 DR_TAG=A12rot DR_H=30
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/detectreplan || exit 1
nohup "$PY" run_t0.py "$@" > results/t0_run_A12rot.log 2>&1 < /dev/null &
echo "A_LAUNCHED pid=$! tag=A12rot log=results/t0_run_A12rot.log"
