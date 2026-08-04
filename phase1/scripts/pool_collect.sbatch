#!/bin/bash
#SBATCH --job-name=pool_collect
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=4
#SBATCH --exclude=projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=08:00:00
#SBATCH --signal=TERM@180
#SBATCH --output=/research/d7/spc/yzyang4/logs/pool_collect_%j.out
refill() { bash /research/d7/spc/yzyang4/scripts/pool_fill_once.sh || true; }
trap 'echo "TERM -> refill before wall-kill" >&2; refill; exit 0' TERM
echo "=== pool batch $PC_ISSUE seeds=$PC_SEEDS job=$SLURM_JOB_ID node=$SLURM_JOB_NODELIST $(date -u +%FT%TZ) ==="
if [ "${PC_RM:-}" = "local" ]; then
  export RM_DIR="${PC_RM_DIR:-/research/d7/spc/yzyang4/models/value_rm/N12000}"
  echo "=== sidecar RM_DIR=$RM_DIR ==="
  /research/d7/spc/yzyang4/venvs/critic/bin/python /research/d7/spc/yzyang4/scripts/rm_server.py > /research/d7/spc/yzyang4/logs/rm_server_$SLURM_JOB_ID.log 2>&1 &
  RM_PID=$!
  RM_UP=0
  for i in $(seq 1 60); do sleep 5; grep -q "listening" /research/d7/spc/yzyang4/logs/rm_server_$SLURM_JOB_ID.log && { RM_UP=1; break; }; done
  if [ "$RM_UP" = "1" ]; then
    export VALUE_RM_URL="http://127.0.0.1:8765"
    export VALUE_RM_LAMBDA="${PC_RM_LAMBDA:-0.5}"
    echo "=== value-RM sidecar up (pid $RM_PID) lambda=$VALUE_RM_LAMBDA ==="
  else
    echo "=== RM_SIDECAR_FAILED: guided arm invalid, batch proceeds as extra control ==="
  fi
fi
S0=$(date +%s)
bash /research/d7/spc/yzyang4/scripts/pool_collect_inner.sh
RC=$?
EL=$(( $(date +%s) - S0 ))
echo "=== batch done rc=$RC elapsed=${EL}s $(date -u +%FT%TZ) ==="
if [ "$EL" -lt 1800 ]; then
  echo "CIRCUIT_BREAK: batch ended after only ${EL}s — NOT chaining next batch (investigate: API/proxy/node)"
else
  refill
fi
