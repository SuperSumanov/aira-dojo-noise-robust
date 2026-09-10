#!/bin/bash
# PREPARED ONLY. Requires a new successful live-route receipt before submission.
#SBATCH --job-name=forets-resilience-pair
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:2
#SBATCH --mem=0
#SBATCH --time=01:15:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ ${FORETS_E2E_MATRIX_APPROVED:-} != 1 || ${FORETS_FREE_ROUTE_CHECKED:-} != 1 ]]; then
    printf '%s\n' 'Missing matrix approval or fresh successful live-route check.' >&2
    exit 2
fi
if [[ $# != 3 || ! -f "$1/forets_e2e_campaign.py" || ! -f "$2/manifest.json" || ! -f "$3" ]]; then
    printf '%s\n' 'Pass code, prepared package, and a successful route receipt.' >&2
    exit 2
fi
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$1/forets_e2e_campaign.py" \
    --package "$2" --execute-approved-matrix --live-route-checked \
    --execution-node gpu28 --run-limit 2 --route-receipt "$3"
