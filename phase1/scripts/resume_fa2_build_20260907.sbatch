#!/usr/bin/env bash
#SBATCH --job-name=fa2_cpu_resume
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpu37
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
: "${FA2_BUILD_CODE_COMMIT:?}"
: "${FA2_BUILD_SCRIPT:?}"
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec /research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python -B "$FA2_BUILD_SCRIPT"
