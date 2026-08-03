#!/bin/bash
#SBATCH --job-name=l2_fast
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --cpus-per-task=6
#SBATCH --time=12:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/l2_fast_%j.out
# An early read on L2 at N=4000, both arms serially on one GPU (~3.5h each including eval),
# so the direction is known this afternoon instead of tomorrow at 04:00. The flip eval runs on
# the FULL 1,134-pair ladder -- that is the metric, so it is not the thing to shrink; the regular
# eval cap is halved instead. N=4000 is also a real point on the scale curve, so if the main run
# lands well this is not wasted.
source ~/env_setup.sh
export PATH="/research/d7/spc/yzyang4/venvs/critic/bin:$PATH"
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
D=/research/d7/spc/yzyang4/aira-dojo/phase1
COMMON="--pairs $D/budget_pairs_matched.jsonl --cards $D/cards_current.jsonl --sizes 4000 \
  --max-len 2048 --eval-cap 1500 --flip-eval $D/budget_flip_matched.jsonl \
  --deepspeed phase1/ds_zero3_offload.json --bs 1 --accum 16 --lr 1e-5 --epochs 2 --seed 7"

echo "=== FAST ARM: BLIND ==="
deepspeed --include localhost:0 --master_port $(( 29000 + (SLURM_JOB_ID % 800) )) \
  phase1/rm_train_hf.py $COMMON --out $D/l2_fast_blind.csv
echo "FAST_BLIND_DONE rc=$?"

echo "=== FAST ARM: BUDGET-CONDITIONED ==="
deepspeed --include localhost:0 --master_port $(( 29810 + (SLURM_JOB_ID % 180) )) \
  phase1/rm_train_hf.py $COMMON --budget-cond --out $D/l2_fast_cond.csv
echo "FAST_COND_DONE rc=$?"
echo "L2_FAST_DONE"
