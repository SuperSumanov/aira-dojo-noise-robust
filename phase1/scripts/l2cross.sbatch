#!/bin/bash
#SBATCH --job-name=l2cross
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=03:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/l2cross_%j.out
# Three eval-only cells on one GPU, sequential (plain python -- no deepspeed launcher,
# eval-only never builds a Trainer so ZeRO is irrelevant):
#   A: v2-trained L2 model  -> v3 pairs + v3 flip sets   (2x2 off-diagonal)
#   B: v3-trained L2 model  -> v2 pairs + v2 flip sets   (2x2 off-diagonal)
#   C: lookahead 0.83 model -> decision pairs            (deployment-alignment cell)
# A/B flags mirror the l2x2 diagonal arms exactly; C mirrors the decision arms exactly.
source ~/env_setup.sh
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
D=phase1
RC=0

echo "=== cell A: ckpt_l2_v2data -> v3 evals $(date -u +%FT%TZ) ==="
RM_DUMP_HITS=$D/hits_l2v2_on_v3.jsonl $P phase1/rm_train_hf.py \
  --pairs $D/budget_pairs_v3.jsonl --cards $D/cards_current.jsonl \
  --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 \
  --budget-cond --budget-pos tail --seed 7 --bs 8 \
  --flip-eval $D/budget_flip_v3.jsonl \
  --eval-ckpt $D/ckpt_l2_v2data/N8000 --out $D/l2x2_cross.csv || RC=1
echo "CELL_A_DONE rc=$RC"

echo "=== cell B: ckpt_l2_v3data -> v2 evals $(date -u +%FT%TZ) ==="
RM_DUMP_HITS=$D/hits_l2v3_on_v2.jsonl $P phase1/rm_train_hf.py \
  --pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl \
  --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 \
  --budget-cond --budget-pos tail --seed 7 --bs 8 \
  --flip-eval $D/budget_flip_v2.jsonl \
  --eval-ckpt $D/ckpt_l2_v3data/N8000 --out $D/l2x2_cross.csv || RC=1
echo "CELL_B_DONE rc=$RC"

echo "=== cell C: ckpt_lookahead_v3 -> decision pairs $(date -u +%FT%TZ) ==="
RM_DUMP_HITS=$D/hits_lookahead_on_decision.jsonl $P phase1/rm_train_hf.py \
  --pairs $D/decision_pairs_v1.jsonl --cards $D/cards_current.jsonl \
  --sizes 24000 --max-len 2048 --eval-cap 900 --eval-len-control 0.15 \
  --seed 7 --bs 8 \
  --eval-ckpt $D/ckpt_lookahead_v3/N24000 --out $D/decision_crosseval.csv || RC=1
echo "CELL_C_DONE rc=$RC"

echo "L2CROSS_DONE rc=$RC $(date -u +%FT%TZ)"
exit $RC
