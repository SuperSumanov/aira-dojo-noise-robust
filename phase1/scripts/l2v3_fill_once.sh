#!/usr/bin/env bash
# L2 on the broadened v3 pairs: spooky is down to 64% of the flip set (was 82-92%) and the
# non-spooky cells (petfinder 308 / birds 245 / chaii 169) are individually powered. Same two
# arms, same recipe, seed 7 first; answers whether the budget effect survives outside spooky.
# Runs on rtx3090 nodes, so it does not contend with T3 rounds on the 2080 pool nodes.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.l2v3_submitted
[ -f "$STATE" ] && exit 0
BASE="--pairs $D/budget_pairs_v3.jsonl --cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --flip-eval $D/budget_flip_v3.jsonl"
if sbatch --job-name=l2v3 --export=ALL,ARM0="$BASE --out $D/l2v3_blind.csv",ARM1="$BASE --budget-cond --budget-pos tail --out $D/l2v3_cond.csv",SEED=7 "$S/train_pool.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted l2 v3 pair (broadened flip set)"
else
  echo "l2v3: QOS full, retry next heartbeat"
fi
