#!/usr/bin/env bash
# Few-shot rescue, pre-registered branch: how many target pairs fix an inverted (nomad) or
# mid-transfer (petfinder) LOTO model. One 2-GPU job, both targets. K=0 anchor = the measured
# LOTO numbers (0.4605 / 0.6480).
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
STATE=$S/.rescue_submitted
[ -f "$STATE" ] && exit 0
COMMON="--cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2000 --eval-len-control 0.15"
if sbatch --job-name=rescue2k --export=ALL,ARM0="--pairs $D/rescue_nomad_k2000.jsonl $COMMON --out $D/rescue_nomad.csv",ARM1="--pairs $D/rescue_petfinder_k2000.jsonl $COMMON --out $D/rescue_petfinder.csv" "$S/train_pool.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted rescue pair (nomad/petfinder K=2000)"
else
  echo "rescue: QOS full, retry next heartbeat"
fi
