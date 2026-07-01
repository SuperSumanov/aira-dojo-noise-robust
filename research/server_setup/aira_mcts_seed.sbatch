#!/bin/bash
#SBATCH --job-name=mcts_t0
#SBATCH --partition=gpu_2h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --cpus-per-task=6
#SBATCH --time=02:00:00
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo-runs/mcts_t0_seed_%j.out
#SBATCH --error=/research/d7/spc/yzyang4/aira-dojo-runs/mcts_t0_seed_%j.out

source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
SEED="${SEED:-1}"
EXP="${EXP:-mlebench/deepseek_mcts}"
ISSUE="${ISSUE:-deepseek_mcts_t0}"
echo "=== MCTS T0 exp=$EXP issue=$ISSUE seed=$SEED on $(hostname) ==="; date -u +%FT%TZ
CUDA_VISIBLE_DEVICES=0 "$VENV/bin/python" -m dojo.main_run +_exp=$EXP \
  logger.use_wandb=False \
  metadata.git_issue_id=$ISSUE \
  metadata.seed="$SEED" \
  solver.step_limit=20 \
  solver.time_limit_secs=6000
echo "MCTS_SEED_${SEED}_DONE rc=$? $(date -u +%FT%TZ)"
