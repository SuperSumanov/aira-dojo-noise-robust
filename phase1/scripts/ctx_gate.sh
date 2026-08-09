#!/usr/bin/env bash
# Context-length sweep: the lever the truncation audit and the senior both point at.
#
# Every result so far came from 1.5B @ 2048, where 84% of programs are truncated and the
# model sees 63% of the tokens -- and what it loses is the middle, where feature
# engineering and leakage live (merge( 25% visible, groupby 40%). Meanwhile the senior
# reports 0.6B/1.7B/4B performing alike on his pairwise runs, and our own 1.5B-vs-0.5B gap
# was small (0.573 vs 0.538). So capacity looks flat and context looks binding; this sweep
# separates the two on one axis at a time.
#
#   A  0.5B @ 8192   99% token coverage, small model      <- the senior's suggestion
#   B  1.5B @ 4096   90% coverage, our usual capacity
#   C  0.5B @ 2048   the capacity control for A
# Existing 1.5B @ 2048 = 0.6493 is the fourth cell, already measured.
#
# All on the run-clean split so numbers are comparable with everything since 08-09.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
D=/research/d7/spc/yzyang4/aira-dojo/phase1
S=/research/d7/spc/yzyang4/scripts
LOG=/research/d7/spc/yzyang4/logs/ctx_gate.log
M05=/research/d7/spc/yzyang4/external/models/qwen2.5-0.5b-instruct
BASE="--pairs $D/value_pairs_runsplit.jsonl --cards $D/cards_current_v7.jsonl --sizes 24000 --eval-cap 3000 --out $D/ctx_sweep.csv"

run_one () {  # $1 tag  $2 extra args
  if grep -q ",$1," "$D/ctx_sweep_tags.txt" 2>/dev/null; then return; fi
  local tries=0
  while :; do
    n=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
    if [ "$n" -lt 4 ]; then
      if sbatch --job-name="ctx_$1" \
           --export=ALL,ARM0="$BASE $2",SEED=7,HITS="$D/hits_ctx_$1.jsonl" \
           "$S/train_pool_hits.sbatch" >> "$LOG" 2>&1; then
        echo ",$1," >> "$D/ctx_sweep_tags.txt"
        echo "$(date -u +%FT%TZ) submitted $1" >> "$LOG"
        sleep 90
        return
      fi
      tries=$((tries+1))
      [ "$tries" -ge 40 ] && { echo "$(date -u +%FT%TZ) GIVE UP $1" >> "$LOG"; return; }
    fi
    sleep 240
  done
}

echo "$(date -u +%FT%TZ) ctx gate up" >> "$LOG"
run_one "05b8192"  "--max-len 8192 --model $M05"
run_one "15b4096"  "--max-len 4096"
run_one "05b2048"  "--max-len 2048 --model $M05"
echo "$(date -u +%FT%TZ) ctx gate done" >> "$LOG"
