#!/bin/bash
# L2 rerun on the audited data. Replaces job 8940, whose value had collapsed: it ran on v1
# (no tau filter, 166 budget-signal records at N=4000) with unstratified eval, and the question
# it was answering -- "is N too small" -- was superseded by finding the real bottleneck.
#
# arm0  v2 blind          the new baseline; the old one is not comparable, different data
# arm1  v2 cond + tail    both fixes at once: denser budget signal AND the budget adjacent to
#                         the pooled token. It cannot separate the two causes, but job 8995
#                         (v1 + tail) isolates position on its own, so the pair of runs does.
#
# N=8000, not 24000: at 14.1% signal density that is ~1128 budget-dependent records versus 166
# before, and code diversity caps out at 1498 distinct programs anyway, so a larger N buys
# recombination rather than information. Finishes overnight instead of tomorrow afternoon.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts

scancel --full --signal=KILL 8940 2>/dev/null
sleep 6

BASE="--pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --flip-eval $D/budget_flip_v2.jsonl"

sbatch --job-name=l2v2 \
  --export=ALL,ARM0="$BASE --out $D/l2v2_blind.csv",ARM1="$BASE --budget-cond --budget-pos tail --out $D/l2v2_cond_tail.csv" \
  "$S/train_pool.sbatch"

squeue -u "$USER" -o "%.8i %.12j %.2t %.11M %R"
