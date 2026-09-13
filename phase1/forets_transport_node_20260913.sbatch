#!/bin/bash
#SBATCH --job-name=forets-transport-diag
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:15:00
#SBATCH --output=/research/d7/spc/yzyang4/logs/forets_transport_%j.out
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
STAGE=/research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD
OUT=$(mktemp -d /research/d7/spc/yzyang4/forets-transport-node-20260913-XXXXXX)
printf '%s\n' "$OUT"
timeout --signal=TERM --kill-after=10s 850s /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$STAGE/diagnose_forets_kernel_transport_20260913.py" "$OUT" --keep-gpu --max-servers 64
