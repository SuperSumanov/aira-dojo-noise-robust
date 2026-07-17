#!/bin/bash
#SBATCH --job-name=saeprobe
#SBATCH --partition=gpu_24h
#SBATCH --exclude=projgpu33
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo/phase1/_logs/sae_%j.out
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/critic/bin/activate
cd /research/d7/spc/yzyang4/aira-dojo
echo "=== SAE start $(date -u +%FT%TZ) ==="
python -m phase1.sae_probe
echo "=== SBATCH_EXIT=$? end $(date -u +%FT%TZ) ==="
