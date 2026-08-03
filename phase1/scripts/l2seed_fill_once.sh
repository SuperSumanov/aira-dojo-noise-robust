#!/usr/bin/env bash
# Seed replication for the L2 verdict (0.522 at 1.75 sigma on seed 7). Three seeds total
# (7, 13, 17) were the plan BEFORE seeing seed 13's result -- no optional stopping. One 2-GPU
# job per seed, both arms inside it, submitted one per free slot. Outranks LOTO folds.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
BASE="--pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --flip-eval $D/budget_flip_v2.jsonl"

for SD in 13 17; do
  STATE=$S/.l2seed_submitted_$SD
  [ -f "$STATE" ] && continue
  if sbatch --job-name=l2v2_s$SD \
       --export=ALL,ARM0="$BASE --out $D/l2v2_blind_s$SD.csv",ARM1="$BASE --budget-cond --budget-pos tail --out $D/l2v2_cond_s$SD.csv",SEED=$SD \
       "$S/train_pool.sbatch" >/dev/null 2>&1; then
    touch "$STATE"
    echo "$(date -u +%FT%TZ) submitted l2v2 seed-$SD pair"
  else
    echo "l2seed: QOS full for seed $SD, retry next heartbeat"
  fi
  exit 0
done
echo "all seeds submitted"
