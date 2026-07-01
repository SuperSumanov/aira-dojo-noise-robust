#!/usr/bin/env bash
# aira-dojo pilot: same as smoke but step_limit=10 / time_limit=1h so the greedy debug loop
# converges to a non-buggy node, and we can measure per-run cost.
set -x
source ~/env_setup.sh

VENV=/research/d7/spc/yzyang4/venvs/aira
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
AIRA=/research/d7/spc/yzyang4/aira-dojo

cd "$AIRA" || { echo "FATAL: aira-dojo missing"; exit 1; }
echo "=== aira-dojo PILOT start ==="; date -u +%FT%TZ
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "no nvidia-smi"

SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" -m dojo.main_run +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.git_issue_id=deepseek_pilot \
  solver.step_limit=10 \
  solver.time_limit_secs=3600
echo "AIRA_PILOT_EXIT=$? elapsed_sec=$SECONDS"
date -u +%FT%TZ

echo "=== latest run dir ==="
ls -lat /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/ 2>/dev/null | head
echo "AIRA_PILOT_DONE"
