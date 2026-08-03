#!/bin/bash
#SBATCH --job-name=pool_deep
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=4
#SBATCH --constraint=rtx2080
#SBATCH --exclude=projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=23:00:00
#SBATCH --signal=TERM@180
#SBATCH --output=/research/d7/spc/yzyang4/logs/pool_deep_%j.out
# DEEP-TREE collection. The standard protocol (step_limit=20, 3.5h) yields a median of 0
# descendants per node, which caps the lookahead work: a count-matched budget of K=5 leaves
# only 2,362 held-out records. This regime lets the wall clock do the truncating instead,
# matching the senior's deep-tree protocol so the two lines' trees are comparable.
# solver.time_limit_secs is set ~2h below the wall on purpose: external grading only lands in
# the journal when the solver exits cleanly, so a wall-kill loses the labels for the whole run.
refill() { bash /research/d7/spc/yzyang4/scripts/deep_fill_once.sh || true; }
trap 'echo "TERM -> refill before wall-kill" >&2; refill; exit 0' TERM
export PC_STEPS=10000
export PC_TIMELIM=75600
export PC_EXECTO="${PC_EXECTO:-7200}"
echo "=== deep batch $PC_ISSUE seeds=$PC_SEEDS job=$SLURM_JOB_ID node=$SLURM_JOB_NODELIST steps=$PC_STEPS timelim=$PC_TIMELIM $(date -u +%FT%TZ) ==="
S0=$(date +%s)
bash /research/d7/spc/yzyang4/scripts/pool_collect_inner.sh
RC=$?
EL=$(( $(date +%s) - S0 ))
echo "=== deep batch done rc=$RC elapsed=${EL}s $(date -u +%FT%TZ) ==="
if [ "$EL" -lt 1800 ]; then
  echo "CIRCUIT_BREAK: batch ended after only ${EL}s — NOT chaining next batch (investigate: API/proxy/node)"
else
  refill
fi
