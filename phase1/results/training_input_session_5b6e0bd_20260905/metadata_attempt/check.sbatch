#!/usr/bin/env bash
#SBATCH --job-name=zero3_cpu_metadata
#SBATCH --partition=gpu_2h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=0
#SBATCH --gres=none
#SBATCH --nodelist=gpu28
#SBATCH --time=00:02:00
#SBATCH --no-requeue
#SBATCH --output=/research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata/slurm-%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
exec /usr/bin/python3 -B /research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata/check.py
