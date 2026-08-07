#!/bin/bash
#SBATCH --job-name=train_hits
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=23:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/train_hits_%j.out
# Single-arm train_pool variant that also exports RM_DUMP_HITS so the final eval writes
# per-pair hits (enables McNemar / subgroup analysis offline without re-running GPU).
# Usage: sbatch --export=ALL,ARM0="<args>",SEED=8,HITS=/path/hits.jsonl scripts/train_pool_hits.sbatch
source ~/env_setup.sh
export PATH="/research/d7/spc/yzyang4/venvs/critic/bin:$PATH"
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
echo "=== train_hits job=$SLURM_JOB_ID node=$SLURM_JOB_NODELIST seed=${SEED:-7} $(date -u +%FT%TZ) ==="
[ -n "${HITS:-}" ] && export RM_DUMP_HITS="$HITS" && rm -f "$HITS" && echo "hits -> $HITS"
PORT=$(( 25000 + ((SLURM_JOB_ID % 5000) * 8) % 40000 ))
deepspeed --include localhost:0 --master_port $PORT phase1/rm_train_hf.py $ARM0 \
  --deepspeed phase1/ds_zero3_offload.json --bs 1 --accum 16 --lr 1e-5 --epochs 2 --seed ${SEED:-7} \
  > /research/d7/spc/yzyang4/logs/train_hits_${SLURM_JOB_ID}_arm0.log 2>&1
RC=$?
echo "ARM0_DONE rc=$RC"
exit $RC
