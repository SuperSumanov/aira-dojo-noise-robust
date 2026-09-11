#!/bin/bash
#SBATCH --job-name=forets-first-pools-s11
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --time=01:24:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export FORETS_SOURCE_COMMIT="$2"
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=01:23:00 \
    /research/d7/spc/yzyang4/venvs/aira/bin/python "$1/forets_current_pool_20260912.py" run --root "$1"
