#!/usr/bin/env bash
# Submit both L2 arms as ONE 2-GPU allocation (train_pool), not two jobs. The QOS caps jobs at
# 4 and GPUs at 8, so packing the arms frees a slot for the deep-tree collection line.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
# Gate: the smoke must show the blind arm at exactly 0.5000 for every budget gap before
# 32 GPU-hours go in. Cleared by hand after reading smoke2.
[ -f /research/d7/spc/yzyang4/scripts/.l2_hold ] && { echo "l2 on hold (smoke not verified)"; exit 0; }
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts
STATE=$S/.l2_submitted
touch "$STATE"
grep -qxF pool "$STATE" && { echo "l2 already submitted"; exit 0; }

BASE="--pairs $D/budget_pairs_matched.jsonl --cards $D/cards_current.jsonl --sizes 24000 --max-len 2048 --eval-cap 3000 --flip-eval $D/budget_flip_matched.jsonl"

if sbatch --job-name=l2_pool \
     --export=ALL,ARM0="$BASE --out $D/l2_blind.csv",ARM1="$BASE --budget-cond --out $D/l2_cond.csv" \
     "$S/train_pool.sbatch"; then
  echo pool >> "$STATE"
  rm -f "$S/.deep_hold"
  echo "$(date -u +%FT%TZ) submitted L2 pool (blind + cond); deep-tree line released"
else
  echo "l2 pool: QOS/GPU full, retry next heartbeat"
fi
