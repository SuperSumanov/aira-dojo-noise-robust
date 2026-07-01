#!/usr/bin/env bash
# Focused pilot: num_drafts=1 so the greedy debug loop concentrates on fixing ONE solution
# (the all-buggy pilot showed debug fixes object-dtype cols one at a time but ran out of steps).
set -x
source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
AIRA=/research/d7/spc/yzyang4/aira-dojo
cd "$AIRA" || { echo "FATAL: aira-dojo missing"; exit 1; }
echo "=== aira-dojo PILOT2 (num_drafts=1) start ==="; date -u +%FT%TZ
SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" -m dojo.main_run +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.git_issue_id=deepseek_pilot2 \
  solver.num_drafts=1 \
  solver.step_limit=12 \
  solver.time_limit_secs=4500
echo "AIRA_PILOT2_EXIT=$? elapsed_sec=$SECONDS"
date -u +%FT%TZ
echo "AIRA_PILOT2_DONE"
