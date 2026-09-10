#!/bin/bash
# Replacement deployment: same image/matrix/budget, actual GPU checks inside allocation.
#SBATCH --job-name=forets-e2e-paired
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:2
#SBATCH --mem=0
#SBATCH --time=04:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ ${FORETS_E2E_MATRIX_APPROVED:-} != 1 || ${FORETS_FREE_ROUTE_CHECKED:-} != 1 ]]; then
    printf '%s\n' 'Missing exact matrix approval or live-route readiness; refusing execution.' >&2
    exit 2
fi
if [[ $# != 2 || ! -f "$1/forets_e2e_campaign.py" || ! -f "$2/manifest.json" ]]; then
    printf '%s\n' 'Pass the prepared code directory and package directory.' >&2
    exit 2
fi
# The login shell does not currently export the outbound proxy. Reuse the
# established remote process setup; suppress output to avoid credential echoes.
if ! source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1; then
    printf '%s\n' 'Remote network environment setup failed.' >&2
    exit 2
fi
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
# Credentials must be installed/injected remotely; never put their value in this file.
# The Python entry refuses to load a critic if OPENROUTER_API_KEY is absent.
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$1/forets_e2e_campaign.py" \
    --package "$2" --execute-approved-matrix --live-route-checked --execution-node gpu28
