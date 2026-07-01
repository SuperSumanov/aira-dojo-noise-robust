#!/usr/bin/env bash
# lambda=0 "mean-of-k" arm: consistency mechanism (k=3) WITHOUT the variance penalty.
# 5 seeds x spaceship. Self-throttling (<=4 in queue), dup-safe, resumable.
source ~/env_setup.sh
SB=/research/d7/spc/yzyang4/scripts/aira_greedy_hce.sbatch
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_mean_submitted.txt
RUNS=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
ISSUE=t1_mean_spaceship-titanic
touch "$STATE"
echo "MEAN_DAEMON_START $(date -u +%FT%TZ) pid=$$"
while :; do
  pending=0
  for s in 1 2 3 4 5; do
    combo="mean|$s"
    grep -qxF "$combo" "$STATE" && continue
    if ls "$RUNS"/user_yzyang4_issue_${ISSUE}/*seed_${s}_*/checkpoint/journal.jsonl >/dev/null 2>&1; then
      echo "$combo" >> "$STATE"; continue
    fi
    pending=1
    q=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
    [ "$q" -ge 4 ] && continue
    if sbatch --export=ALL,SEED=$s,ARM=consistency,LAM=0,EXP=mlebench/deepseek_greedy_hce_spaceship,ISSUE=$ISSUE "$SB"; then
      echo "$combo" >> "$STATE"; echo "[$(date -u +%FT%TZ)] submitted mean seed=$s"; sleep 5
    else
      echo "[$(date -u +%FT%TZ)] sbatch failed seed=$s; backoff 60s"; sleep 60
    fi
  done
  [ "$pending" = 0 ] && { echo "MEAN_DAEMON_DONE $(date -u +%FT%TZ)"; break; }
  sleep 120
done
