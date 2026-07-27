#!/bin/bash
#SBATCH --job-name=regrade
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=07:30:00
#SBATCH --signal=B:TERM@240
#SBATCH --exclude=projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/regrade_%j.out
source ~/env_setup.sh
export REGRADE_WORK=/tmp/regrade_$SLURM_JOB_ID
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
PY=/research/d7/spc/yzyang4/venvs/exp/bin/python
resubmit_if_left() {
  LEFT=$($PY /research/d7/spc/yzyang4/scripts/regrade_worker.py ${REGRADE_ARGS:-} --limit 0 --dry-count 2>/dev/null | tail -1)
  if [ "${LEFT:-0}" -gt 0 ] 2>/dev/null; then
    sbatch --export=ALL,REGRADE_ARGS="$REGRADE_ARGS" /research/d7/spc/yzyang4/scripts/regrade.sbatch && echo "CHAINED next gen (left=$LEFT)"
  else
    echo "REGRADE_ALL_DONE"
  fi
}
$PY /research/d7/spc/yzyang4/scripts/regrade_worker.py "$@" ${REGRADE_ARGS:-} &
CHILD=$!
trap 'echo WALL_TERM; kill $CHILD 2>/dev/null; resubmit_if_left; exit 0' TERM
wait $CHILD
echo "REGRADE_SBATCH_DONE rc=$?"
resubmit_if_left
