#!/bin/bash
#SBATCH --job-name=forets-identity-diag
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:08:00
#SBATCH --output=/research/d7/spc/yzyang4/logs/forets_identity_%j.out
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
OUT=$(mktemp -d /research/d7/spc/yzyang4/forets-identity-node-20260913-XXXXXX)
printf '%s\n' "$OUT"
timeout --signal=TERM --kill-after=10s 450s /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD/compare_jupyter_session_identity_20260913.py "$OUT"
