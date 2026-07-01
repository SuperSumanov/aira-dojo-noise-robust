#!/usr/bin/env bash
# Quick validation of the draft categorical/simple-first guardrail: 1 draft + 2 steps.
# If node 1 (draft) is non-buggy with a metric, the guardrail fixed the all-buggy issue.
set -x
source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || { echo FATAL; exit 1; }
SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" -m dojo.main_run +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.git_issue_id=deepseek_guard4 \
  solver.num_drafts=1 \
  solver.step_limit=4 \
  solver.time_limit_secs=2400
echo "GUARDTEST_EXIT=$? elapsed_sec=$SECONDS"
echo "GUARDTEST_DONE"
