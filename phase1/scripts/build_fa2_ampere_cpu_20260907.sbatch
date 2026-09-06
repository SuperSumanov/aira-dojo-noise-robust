#!/usr/bin/env bash
# Additional isolated build for the explicitly separate two-RTX3090 route.
#SBATCH --job-name=critic_fa2_ampere
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpu37
#SBATCH --constraint=highcpucount
#SBATCH --mem=0
#SBATCH --time=01:30:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --no-requeue
set -euo pipefail
umask 077
: "${FA2_BUILD_CODE_COMMIT:?}"
: "${FA2_BUILD_SCRIPT:?}"
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python -B "$FA2_BUILD_SCRIPT"
