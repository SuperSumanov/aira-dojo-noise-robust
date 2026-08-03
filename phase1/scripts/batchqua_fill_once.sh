#!/usr/bin/env bash
# Submit the batch-qua-batch diagnostic when a QOS slot frees. One training, two matched test
# sets (TREEHOLD:: vs BATCHHOLD::) -- the gap between them is the isolated batch effect, within
# one protocol, one generator, one recipe. Runs once; outranks the remaining LOTO folds because
# it decides how the paper's central "collapse" chapter must be framed.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.batchqua_submitted
[ -f "$STATE" ] && exit 0

A="--pairs $D/batchqua_pairs.jsonl --cards $D/cards_current.jsonl --sizes 4719 \
--max-len 2048 --eval-cap 999 --out $D/batchqua.csv"
if sbatch --job-name=batchqua --export=ALL,FT_ARGS="$A" "$S/rm_fullft23.sbatch" >/dev/null 2>&1; then
  touch "$STATE"
  echo "$(date -u +%FT%TZ) submitted batch-qua-batch diagnostic"
else
  echo "batchqua: QOS full, retry next heartbeat"
fi
