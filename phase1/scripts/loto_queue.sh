#!/usr/bin/env bash
# Leave-one-task-out for lookahead. Each run trains on every other task and is tested only on
# the held-out one, so the number is per-task by construction and cannot be inflated by spooky
# dominating a pooled test set -- which is exactly what made the global 0.7640 misleading.
#
# Targets to beat, from the training-free per-task baselines:
#   birds     self_report 0.5163   (in-distribution model got 0.411 -- worse than chance)
#   chaii     self_report 0.6117
#   petfinder self_report 0.7277
#   nomad     self_report 0.5232
# Held-out pair counts are 22482 / 22534 / 26537 / 7058, all large enough to resolve a gap.
#
# Submitted one at a time as GPUs free up; the heartbeat retries when the QOS is full.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts
STATE=$S/.loto_submitted
touch "$STATE"

for T in mlsp-2013-birds chaii-hindi-and-tamil-question-answering \
         petfinder-pawpularity-score nomad2018-predict-transparent-conductors; do
  grep -qxF "$T" "$STATE" && continue
  A="--pairs $D/budget_pairs_matched.jsonl --cards $D/cards_current.jsonl --sizes 4000 \
--max-len 2048 --eval-cap 2000 --loto $T --out $D/loto_lookahead.csv"
  if sbatch --job-name="loto_${T:0:6}" --export=ALL,FT_ARGS="$A" "$S/rm_fullft23.sbatch" >/dev/null 2>&1; then
    echo "$T" >> "$STATE"
    echo "$(date -u +%FT%TZ) submitted LOTO $T"
    exit 0            # one per invocation; the heartbeat brings the next when a slot frees
  else
    echo "LOTO $T: no slot, retry next heartbeat"
    exit 0
  fi
done
echo "all LOTO tasks submitted"
