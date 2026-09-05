#!/usr/bin/env bash
# QOS requires a GPU; this allocation is charged although no model runs.
#SBATCH --job-name=critic_cuda_metadata_r2
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=0
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --nodelist=gpu28
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=00:01:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/research/d7/spc/yzyang4/toolchain-metadata-gpu28-20260906-r2/code
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/exp/bin/python -m phase1.scripts.inspect_gpu28_cuda_toolchains_r2_20260906
