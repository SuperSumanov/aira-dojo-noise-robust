#!/usr/bin/env bash
# 4-GPU pool COLLECTION (container path, MCTS 20-step): one salloc, srun_pool max_parallel=4.
# Env knobs: PC_TASKS (default tps_may+tps_dec), PC_SEEDS (default [601,602,603,604]), PC_ISSUE, PC_PAR.
source ~/env_setup.sh
cd /research/d7/spc/yzyang4/aira-dojo-reproduce || exit 1
set -a; source .env; set +a
export DEFAULT_SLURM_ACCOUNT="${DEFAULT_SLURM_ACCOUNT:-gpu}"
export DEFAULT_SLURM_PARTITION="${DEFAULT_SLURM_PARTITION:-gpu_24h}"
export DEFAULT_SLURM_QOS="${DEFAULT_SLURM_QOS:-gpu}"
export PYTHONPATH=/research/d7/spc/yzyang4/aira-dojo-reproduce/src
if [ -n "${PC_TASKS_SC:-}" ]; then PC_TASKS=$(echo "$PC_TASKS_SC" | tr ";" ","); else PC_TASKS="${PC_TASKS:-tabular-playground-series-may-2022,tabular-playground-series-dec-2021}"; fi
if [ -n "${PC_S1:-}" ]; then PC_SEEDS="[${PC_S1},${PC_S2}]"; else PC_SEEDS="${PC_SEEDS:-[601,602]}"; fi
PC_ISSUE="${PC_ISSUE:-mcts_data_poolC1}"
PC_PAR="${PC_PAR:-4}"
PC_DEBUG="${PC_DEBUG:-false}"
echo "=== pool_collect start $(date -u +%FT%TZ) alloc=${SLURM_JOB_ID:-none} node=${SLURM_JOB_NODELIST:-none} tasks=$PC_TASKS seeds=$PC_SEEDS par=$PC_PAR ==="
/research/d7/spc/yzyang4/venvs/aira/bin/python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  "benchmark.tasks=[$PC_TASKS]" \
  "vars={metadata.seed:$PC_SEEDS}" \
  solver=mlebench/mcts \
  "solver/client@solver.operators.analyze.llm.client=${PC_CLIENT:-litellm_deepseek_flash}" \
  "solver/client@solver.operators.debug.llm.client=${PC_CLIENT:-litellm_deepseek_flash}" \
  "solver/client@solver.operators.draft.llm.client=${PC_CLIENT:-litellm_deepseek_flash}" \
  "solver/client@solver.operators.improve.llm.client=${PC_CLIENT:-litellm_deepseek_flash}" \
  solver.step_limit=${PC_STEPS:-20} \
  solver.execution_timeout=${PC_EXECTO:-1500} \
  solver.time_limit_secs=${PC_TIMELIM:-12600} \
  metadata.git_issue_id=$PC_ISSUE \
  launcher=srun_pool \
  '~launcher.qos' \
  launcher.debug=$PC_DEBUG \
  launcher.max_parallel=$PC_PAR \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  launcher.min_remaining_seconds_to_launch=1800 \
  logger.use_wandb=false
echo "=== pool_collect done rc=$? $(date -u +%FT%TZ) ==="
