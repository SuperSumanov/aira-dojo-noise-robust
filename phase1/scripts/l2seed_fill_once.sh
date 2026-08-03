#!/usr/bin/env bash
# Seed replication for the L2 verdict (0.522 at 1.75 sigma, single seed). One 2-GPU job, both
# arms at seed 13. Outranks the remaining LOTO folds: the L2 effect is the go/no-go for the
# budget-conditioning chapter, LOTO folds are additive coverage.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.l2seed_submitted
[ -f "$STATE" ] && exit 0
BASE="--pairs $D/budget_pairs_v2.jsonl --cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --flip-eval $D/budget_flip_v2.jsonl"
if sbatch --job-name=l2v2_s13 --export=ALL,ARM0="$BASE --out $D/l2v2_blind_s13.csv",ARM1="$BASE --budget-cond --budget-pos tail --out $D/l2v2_cond_s13.csv",SEED=13 "$S/train_pool.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted l2v2 seed-13 pair"
else
  echo "l2seed: QOS full, retry next heartbeat"
fi
