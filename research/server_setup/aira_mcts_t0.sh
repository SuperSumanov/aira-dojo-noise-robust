#!/usr/bin/env bash
# Collect a baseline AIRA_MCTS tree (DeepSeek, spaceship-titanic) for T0.
# Each valid node records BOTH the self-reported validation metric (node.metric) used for search,
# and the external pristine score in node.metric.info["score"] (the T0 "true value").
set -x
source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || { echo "FATAL: aira-dojo missing"; exit 1; }
echo "=== AIRA_MCTS T0 tree start ==="; date -u +%FT%TZ
SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" -m dojo.main_run +_exp=mlebench/deepseek_mcts \
  logger.use_wandb=False \
  metadata.git_issue_id=deepseek_mcts_t0 \
  metadata.seed=1 \
  solver.step_limit=20 \
  solver.time_limit_secs=6000
echo "MCTS_T0_EXIT=$? elapsed_sec=$SECONDS"; date -u +%FT%TZ
echo "MCTS_T0_DONE"
