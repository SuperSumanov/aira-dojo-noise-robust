#!/bin/bash
#SBATCH --job-name=pool_collect
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=4
#SBATCH --time=08:00:00
#SBATCH --signal=TERM@180
# account/qos/partition/exclude/output are supplied by pool_fill_once.sh via CLI flags (portable).
# Requires env (via --export=ALL from the submitter's shell): COLLECT_HOME, DOJO_REPO (+PC_* knobs).
refill() { bash "$DOJO_REPO/scripts/collect/pool_fill_once.sh" || true; }
trap 'echo "TERM -> refill before wall-kill" >&2; refill; exit 0' TERM
echo "=== pool batch ${PC_ISSUE:-?} seeds=[${PC_S1:-?},${PC_S2:-?}] job=$SLURM_JOB_ID node=$SLURM_JOB_NODELIST $(date -u +%FT%TZ) ==="
S0=$(date +%s)
bash "$DOJO_REPO/scripts/collect/pool_collect_inner.sh"
RC=$?
EL=$(( $(date +%s) - S0 ))
echo "=== batch done rc=$RC elapsed=${EL}s $(date -u +%FT%TZ) ==="
if [ "$EL" -lt 1800 ]; then
  echo "CIRCUIT_BREAK: batch ended after only ${EL}s - NOT chaining (check API/proxy/node before re-arming)"
else
  refill
fi
