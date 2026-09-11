#!/bin/bash
# Fresh seed10 development block; never reuse the closed seed8/9 outputs.
#SBATCH --job-name=forets-env-s10
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:2
#SBATCH --mem=0
#SBATCH --time=04:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B \
  /research/d7/spc/yzyang4/forets-env-20260912-edcpizid/code/forets_native_run_20260911.py execute --block 1
