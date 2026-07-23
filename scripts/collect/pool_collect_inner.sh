#!/usr/bin/env bash
# pool_collect_inner.sh — one collection batch: srun_pool over PC_TASKS x seeds [PC_S1,PC_S2], MCTS 20-step.
# Env knobs: PC_S1/PC_S2 (seeds), PC_TASKS_SC (semicolon-joined task list; commas break sbatch --export),
#            PC_ISSUE (fresh id per batch — batch/manifest reuse gotcha), PC_PAR (default 4),
#            PC_EXECTO (per-exec cap seconds; 1500 tabular/text, 3600 vision/audio), PC_DEBUG.
set -u
: "${COLLECT_HOME:?}"; : "${DOJO_REPO:?}"
[ -f "$HOME/env_setup.sh" ] && source "$HOME/env_setup.sh"   # proxy etc. (optional)
cd "$DOJO_REPO" || exit 1
set -a; source .env; set +a
export DEFAULT_SLURM_ACCOUNT="${DEFAULT_SLURM_ACCOUNT:-gpu}"
export DEFAULT_SLURM_PARTITION="${DEFAULT_SLURM_PARTITION:-gpu_24h}"
export DEFAULT_SLURM_QOS="${DEFAULT_SLURM_QOS:-gpu}"
export PYTHONPATH="$DOJO_REPO/src"
PY="${DOJO_VENV:-$COLLECT_HOME/venvs/aira}/bin/python"
if [ -n "${PC_TASKS_SC:-}" ]; then PC_TASKS=$(echo "$PC_TASKS_SC" | tr ";" ","); else PC_TASKS="${PC_TASKS:-tabular-playground-series-may-2022,tabular-playground-series-dec-2021}"; fi
PC_SEEDS="[${PC_S1:-601},${PC_S2:-602}]"
echo "=== pool_collect start $(date -u +%FT%TZ) alloc=${SLURM_JOB_ID:-none} tasks=$PC_TASKS seeds=$PC_SEEDS execto=${PC_EXECTO:-1500} ==="
"$PY" -m dojo.main_runner_job_array \
  +_exp=runner_example \
  "benchmark.tasks=[$PC_TASKS]" \
  "vars={metadata.seed:$PC_SEEDS}" \
  solver=mlebench/mcts \
  'solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash' \
  solver.step_limit=20 \
  solver.execution_timeout=${PC_EXECTO:-1500} \
  solver.time_limit_secs=12600 \
  metadata.git_issue_id=${PC_ISSUE:-mcts_data_pool} \
  launcher=srun_pool \
  '~launcher.qos' \
  launcher.debug=${PC_DEBUG:-false} \
  launcher.max_parallel=${PC_PAR:-4} \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  launcher.min_remaining_seconds_to_launch=1800 \
  logger.use_wandb=false
echo "=== pool_collect done rc=$? $(date -u +%FT%TZ) ==="
