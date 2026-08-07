#!/bin/bash
#SBATCH --job-name=l1clean
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=02:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/l1clean_%j.out
# L1 cleanliness audit. value_pairs.py labels a pair "test" when EITHER endpoint is in a
# held tree (train side is tree-pure, but test pairs mix novel-vs-seen-tree comparisons).
# Re-run the lookahead checkpoint on the same 3000-pair eval (cap 3000, no stratify, seed 7
# -- the rm_lookahead_strong geometry) dumping per-pair hits; offline join then splits
# clean (both trees held) vs mixed (one tree seen in training) accuracy.
source ~/env_setup.sh
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
D=phase1
rm -f $D/hits_l1_valuepairs.jsonl
RM_DUMP_HITS=$D/hits_l1_valuepairs.jsonl $P phase1/rm_train_hf.py \
  --pairs $D/value_pairs_v3.jsonl --cards $D/cards_current.jsonl \
  --sizes 24000 --max-len 2048 --eval-cap 3000 \
  --seed 7 --bs 8 \
  --eval-ckpt $D/ckpt_lookahead_v3/N24000 --out $D/l1_clean_audit.csv
RC=$?
echo "L1CLEAN_DONE rc=$RC $(date -u +%FT%TZ)"
exit $RC
