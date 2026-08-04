#!/usr/bin/env bash
# Retrain the 0.8183 lookahead model with a saved checkpoint (the original run did not save).
# Exact recipe of job 8937: value_pairs_v3, N=24000, full FT, 2 epochs, seed 7, max_len 2048.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.t3model_submitted
[ -f "$STATE" ] && exit 0
A="--pairs $D/value_pairs_v3.jsonl --cards $D/cards_current.jsonl --sizes 24000 --max-len 2048 --eval-cap 3000 --save-adapter $D/ckpt_lookahead_v3 --out $D/rm_lookahead_strong.csv"
if sbatch --job-name=t3model --export=ALL,FT_ARGS="$A" "$S/rm_fullft23.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted t3 model retrain (saved this time)"
else
  echo "t3model: QOS full, retry next heartbeat"
fi
