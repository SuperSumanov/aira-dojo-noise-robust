#!/bin/bash
#SBATCH --job-name=l2diag
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=03:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/l2diag_%j.out
# Measurement-path arbitration. The cross cells (offline eval-only, bs 8) scored ~10 pts
# ABOVE the diagonals (in-process ZeRO-3 eval at end of training, eval bs 2) on the same
# test sets. Recompute both diagonals offline to separate:
#   D: v2 ckpt -> v2 evals, bs 8   E: v3 ckpt -> v3 evals, bs 8   F: v2 ckpt -> v2 evals, bs 1
# (i) D,E ~ cross level & F ~ D  -> in-process eval degraded; offline numbers are truth
# (ii) D,E ~ in-process level    -> cross>diag is a real protocol effect
# (iii) D high but F low         -> batch-size-dependent eval bug; cross cells suspect
source ~/env_setup.sh
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
D=phase1
RC=0

echo "=== cell D: ckpt_l2_v2data -> v2 evals bs8 $(date -u +%FT%TZ) ==="
$P phase1/rm_train_hf.py \
  --pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl \
  --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 \
  --budget-cond --budget-pos tail --seed 7 --bs 8 \
  --flip-eval $D/budget_flip_v2.jsonl \
  --eval-ckpt $D/ckpt_l2_v2data/N8000 --out $D/l2x2_diag_offline.csv || RC=1
echo "CELL_D_DONE rc=$RC"

echo "=== cell E: ckpt_l2_v3data -> v3 evals bs8 $(date -u +%FT%TZ) ==="
$P phase1/rm_train_hf.py \
  --pairs $D/budget_pairs_v3.jsonl --cards $D/cards_current.jsonl \
  --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 \
  --budget-cond --budget-pos tail --seed 7 --bs 8 \
  --flip-eval $D/budget_flip_v3.jsonl \
  --eval-ckpt $D/ckpt_l2_v3data/N8000 --out $D/l2x2_diag_offline.csv || RC=1
echo "CELL_E_DONE rc=$RC"

echo "=== cell F: ckpt_l2_v2data -> v2 evals bs1 (in-process eval geometry) $(date -u +%FT%TZ) ==="
$P phase1/rm_train_hf.py \
  --pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl \
  --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 \
  --budget-cond --budget-pos tail --seed 7 --bs 1 \
  --flip-eval $D/budget_flip_v2.jsonl \
  --eval-ckpt $D/ckpt_l2_v2data/N8000 --out $D/l2x2_diag_offline.csv || RC=1
echo "CELL_F_DONE rc=$RC"

echo "L2DIAG_DONE rc=$RC $(date -u +%FT%TZ)"
exit $RC
