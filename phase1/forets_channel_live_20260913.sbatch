#!/bin/bash
#SBATCH --job-name=forets-channel-live
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:05:00
#SBATCH --output=/research/d7/spc/yzyang4/logs/forets_channel_%j.out
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
timeout --signal=TERM --kill-after=10s 280s /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD/verify_forets_initial_channel_live_20260913.py /research/d7/spc/yzyang4/forets-wallclock-20260912-xc26fkd0
