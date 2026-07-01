#!/usr/bin/env bash
# Run the DetectReplan FLOOR gate on linux5 (zero GPU; API via proxy). Key from remote-only .env.
# Usage: bash dr_run_floor.sh [N] [model] [seed0]
source ~/env_setup.sh 2>/dev/null
source /research/d7/spc/yzyang4/detectreplan/.env
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/detectreplan || exit 1
"$PY" run_floor.py "$@"
