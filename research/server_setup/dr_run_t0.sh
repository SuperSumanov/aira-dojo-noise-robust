#!/usr/bin/env bash
# Run the DetectReplan 2x2 T0 (foreground). Usage: bash dr_run_t0.sh [N] [model] [seed0] [workers]
source ~/env_setup.sh 2>/dev/null
source /research/d7/spc/yzyang4/detectreplan/.env
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/detectreplan || exit 1
"$PY" run_t0.py "$@"
