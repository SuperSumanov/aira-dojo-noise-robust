#!/bin/bash
#SBATCH --job-name=mcsmoke
#SBATCH --partition=gpu_24h
#SBATCH --exclude=projgpu33
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=01:00:00
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo/phase1/_logs/mcsmoke_%j.out

source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || { echo FATAL_no_aira; exit 1; }
echo "=== morecards smoke (nomad MCTS step=3 seed=921) start $(date -u +%FT%TZ) ==="
nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo no-smi
CUDA_VISIBLE_DEVICES=0 "$VENV/bin/python" -m dojo.main_run +_exp=mlebench/deepseek_mcts_nomad \
  logger.use_wandb=False \
  metadata.git_issue_id=morecards_smoke_nomad \
  metadata.seed=921 \
  solver.step_limit=3 \
  solver.time_limit_secs=1500
echo "=== SMOKE_EXIT=$? end $(date -u +%FT%TZ) ==="
