#!/usr/bin/env bash
# One CPU-only inventory. No GPU requests, imports, model run or installation.
#SBATCH --job-name=critic_cuda_metadata
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --nodelist=gpu28
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=00:02:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1
readonly root=/research/d7/spc/yzyang4/toolchain-metadata-gpu28-20260906
exec /research/d7/spc/yzyang4/venvs/exp/bin/python "$root/inspect_gpu28_cuda_toolchains_20260906.py"
