#!/usr/bin/env bash
#SBATCH --job-name=critic_fa2_build
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpu28
#SBATCH --mem=24G
#SBATCH --time=00:40:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --no-requeue
set -euo pipefail
umask 077
: "${FA2_BUILD_CODE_COMMIT:?}"
: "${FA2_BUILD_SCRIPT:?}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python -B "$FA2_BUILD_SCRIPT"
