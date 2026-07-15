#!/bin/bash
#SBATCH --job-name=b1det
#SBATCH --partition=gpu_24h
#SBATCH --exclude=projgpu33
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo/phase1/_logs/b1_%j.out

source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/critic/bin/activate
cd /research/d7/spc/yzyang4/aira-dojo
echo "=== host $(hostname) gpu $CUDA_VISIBLE_DEVICES start $(date -u +%FT%TZ) ==="
python -m phase1.b1_detector
echo "=== SBATCH_EXIT=$? end $(date -u +%FT%TZ) ==="
