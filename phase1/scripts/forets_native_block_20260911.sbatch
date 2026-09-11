#!/bin/bash
# Two fixed blocks are submitted sequentially, never a previous pool resume.
#SBATCH --job-name=forets-native-block
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:2
#SBATCH --mem=0
#SBATCH --time=04:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
if [[ $# != 2 || ! -f "$1/forets_native_run_20260911.py" || ! "$2" =~ ^[12]$ ]]; then
    printf '%s\n' 'Exact release directory and block 1/2 required.' >&2
    exit 2
fi
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$1/forets_native_run_20260911.py" execute --block "$2"
