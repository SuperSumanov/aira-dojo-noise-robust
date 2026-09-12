#!/bin/bash
#SBATCH --job-name=forets-readiness-diagnostic
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=8G
#SBATCH --time=00:35:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
srun --exclusive --exact --ntasks=1 --cpus-per-task=6 --gres=gpu:1 /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-readiness-live-20260912-i3uww4ec/forets_readiness_live_20260912.py --commit "$1"
