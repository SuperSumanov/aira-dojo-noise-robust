#!/usr/bin/env bash
# Second dose point of the rescue curve (K=500; same rng seed makes it a nested subset of the
# K=2000 sample). Fires when the K=2000 pair frees its GPUs.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.rescue500_submitted
[ -f "$STATE" ] && exit 0
COMMON="--cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2000 --eval-len-control 0.15"
if sbatch --job-name=rescue500 --export=ALL,ARM0="--pairs $D/rescue_nomad_k500.jsonl $COMMON --out $D/rescue_nomad.csv",ARM1="--pairs $D/rescue_petfinder_k500.jsonl $COMMON --out $D/rescue_petfinder.csv" "$S/train_pool.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted rescue K=500 pair"
else
  echo "rescue500: QOS full, retry next heartbeat"
fi
