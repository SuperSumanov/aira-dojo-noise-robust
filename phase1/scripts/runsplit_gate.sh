#!/bin/bash
# Submit the three run-split retrains as QOS slots free (submit cap = 4 jobs).
# Longest first. Log everything; die quietly if a submission keeps failing.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts
LOG=/research/d7/spc/yzyang4/logs/runsplit_gate.log
echo "$(date -u +%FT%TZ) gate up" >> "$LOG"

sub() { # $1 name  $2 arm  $3 hits
  local tries=0
  while :; do
    n=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
    if [ "$n" -lt 4 ]; then
      if sbatch --job-name="$1" --export=ALL,ARM0="$2",SEED=7,HITS="$3" \
           "$S/train_pool_hits.sbatch" >> "$LOG" 2>&1; then
        echo "$(date -u +%FT%TZ) submitted $1" >> "$LOG"
        return 0
      fi
      tries=$((tries+1))
      [ "$tries" -ge 20 ] && { echo "$(date -u +%FT%TZ) GIVING UP on $1" >> "$LOG"; return 1; }
    fi
    sleep 180
  done
}

sub l1run "--pairs $D/value_pairs_runsplit.jsonl --cards $D/cards_current.jsonl --sizes 24000 --eval-cap 3000 --max-len 2048 --save-adapter $D/ckpt_l1_runsplit --out $D/l1_runsplit.csv" "$D/hits_l1_runsplit.jsonl"
sub l2run "--pairs $D/budget_pairs_v3_runsplit.jsonl --cards $D/cards_current.jsonl --sizes 8000 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --max-len 2048 --budget-cond --budget-pos tail --flip-eval $D/budget_flip_v3_runsplit.jsonl --out $D/l2_runsplit.csv" "$D/hits_l2_runsplit.jsonl"
sub decrun7 "--pairs $D/decision_pairs_runsplit.jsonl --cards $D/cards_current.jsonl --sizes 4000 --eval-cap 1400 --eval-len-control 0.15 --max-len 2048 --out $D/decision_runsplit.csv" "$D/hits_decrun_s7.jsonl"
echo "$(date -u +%FT%TZ) gate done" >> "$LOG"
