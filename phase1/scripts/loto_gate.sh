#!/usr/bin/env bash
# C2: run all 10 leave-one-task-out folds on value_pairs_v4, one config, as slots free.
#
# The five existing folds were trained on value_pairs_v3, built from the older corpus; a
# different training set makes their accuracies incomparable with new folds, so every fold
# is re-run here on v4. Task list is fixed by the pre-registration (>=2000 pairs in v4 and
# >=40 dual-scored cards in v7) and must not be edited after results appear.
#
# LOTO holds out an entire task, so no run from the evaluated task is in training -- this
# split is immune to the run-level leakage that forced every in-task number down.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts
LOG=/research/d7/spc/yzyang4/logs/loto_gate.log
C="--pairs $D/value_pairs_v4.jsonl --cards $D/cards_current_v7.jsonl --sizes 4000 --max-len 2048 --eval-cap 2000 --eval-stratify --out $D/loto_v4.csv"

TASKS="chaii-hindi-and-tamil-question-answering petfinder-pawpularity-score spooky-author-identification mlsp-2013-birds nomad2018-predict-transparent-conductors tabular-playground-series-may-2022 tweet-sentiment-extraction google-quest-challenge tabular-playground-series-dec-2021 us-patent-phrase-to-phrase-matching"

echo "$(date -u +%FT%TZ) loto gate up (10 folds)" >> "$LOG"
for T in $TASKS; do
  if grep -q "loto:$T," "$D/loto_v4.csv" 2>/dev/null; then
    echo "$(date -u +%FT%TZ) skip $T (already in loto_v4.csv)" >> "$LOG"
    continue
  fi
  tries=0
  while :; do
    n=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
    if [ "$n" -lt 4 ]; then
      if sbatch --job-name="loto_${T:0:8}" \
          --export=ALL,ARM0="$C --loto $T",SEED=7 \
          "$S/train_pool1.sbatch" >> "$LOG" 2>&1; then
        echo "$(date -u +%FT%TZ) submitted $T" >> "$LOG"
        sleep 60          # let the allocation register before counting slots again
        break
      fi
      tries=$((tries+1))
      [ "$tries" -ge 30 ] && { echo "$(date -u +%FT%TZ) GIVE UP $T" >> "$LOG"; break; }
    fi
    sleep 240
  done
done
echo "$(date -u +%FT%TZ) loto gate done" >> "$LOG"
