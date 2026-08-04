#!/bin/bash
#SBATCH --job-name=train_pool
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:rtx3090:2
#SBATCH --time=23:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/train_pool_%j.out
# Several independent single-GPU trainings inside ONE allocation. The QOS caps job COUNT at 4
# but GPU count at 8, so packing runs into one multi-GPU job buys parallelism the 4-job limit
# would otherwise deny -- collection and training no longer queue behind each other.
#
# DeepSpeed ignores CUDA_VISIBLE_DEVICES whenever --num_gpus/--include is passed (it says so in
# its own startup log), so pinning by that env var silently puts every arm on GPU 0. Pin with
# --include localhost:<idx> instead, and give each arm its own master port.
#
# Usage: sbatch --export=ALL,ARM0="<args>",ARM1="<args>" scripts/train_pool.sbatch
source ~/env_setup.sh
export PATH="/research/d7/spc/yzyang4/venvs/critic/bin:$PATH"
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
echo "=== train_pool job=$SLURM_JOB_ID node=$SLURM_JOB_NODELIST gpus=$(nvidia-smi -L | wc -l) $(date -u +%FT%TZ) ==="
nvidia-smi -L

PIDS=""
for i in 0 1 2 3 4 5 6 7; do
  eval "A=\${ARM$i:-}"
  [ -z "$A" ] && continue
  # stride 8 per job id so co-located jobs can never collide (9036 arm1 hit 9043 arm0:
  # old formula made jobid-diff 7 equal the arm offset 7)
  PORT=$(( 25000 + ((SLURM_JOB_ID % 5000) * 8 + i) % 40000 ))
  echo "--- arm $i on GPU $i port $PORT: $A"
  deepspeed --include "localhost:$i" --master_port $PORT phase1/rm_train_hf.py $A \
    --deepspeed phase1/ds_zero3_offload.json --bs 1 --accum 16 --lr 1e-5 --epochs 2 --seed ${SEED:-7} \
    > /research/d7/spc/yzyang4/logs/train_pool_${SLURM_JOB_ID}_arm$i.log 2>&1 &
  PIDS="$PIDS $!:$i"
done

RC=0
for p in $PIDS; do
  pid=${p%%:*}; idx=${p##*:}
  wait "$pid"; r=$?
  echo "ARM${idx}_DONE rc=$r"
  [ "$r" -ne 0 ] && RC=1
done
echo "TRAIN_POOL_DONE rc=$RC"
