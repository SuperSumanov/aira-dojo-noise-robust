#!/bin/bash
#SBATCH --job-name=forets-pool-completion
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=01:28:00 timeout --signal=TERM --kill-after=10s 5200s /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$1/forets_pool_completion_20260912.py" execute --root "$1"
