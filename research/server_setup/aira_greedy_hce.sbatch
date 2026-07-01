#!/bin/bash
#SBATCH --job-name=t1_hce
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --exclude=projgpu8
#SBATCH --cpus-per-task=6
#SBATCH --time=05:00:00
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_%j.out
#SBATCH --error=/research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_%j.out

source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
SEED="${SEED:-1}"
ARM="${ARM:-full}"
LAM="${LAM:-1.0}"
EXP="${EXP:-mlebench/deepseek_greedy_hce_spaceship}"
ISSUE="${ISSUE:-t1_hce}"
echo "=== T1 HCE arm=$ARM lambda=$LAM exp=$EXP issue=$ISSUE seed=$SEED on $(hostname) ==="; date -u +%FT%TZ
CUDA_VISIBLE_DEVICES=0 "$VENV/bin/python" -m dojo.main_run +_exp=$EXP \
  task.arm=$ARM \
  task.lambda_var=$LAM \
  logger.use_wandb=False \
  metadata.git_issue_id=$ISSUE \
  metadata.seed="$SEED" \
  solver.step_limit=20 \
  solver.time_limit_secs=14400
echo "T1_HCE_${ARM}_${SEED}_DONE rc=$? $(date -u +%FT%TZ)"
