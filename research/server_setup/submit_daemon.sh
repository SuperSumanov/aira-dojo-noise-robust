#!/usr/bin/env bash
# Persistent self-throttling submitter for the T1 matrix: keep the queue filled to 4 until all 30
# combos are submitted. Shares the state file with fill_queue.sh (continues from wave 1). Dup-safe.
source ~/env_setup.sh
SB=/research/d7/spc/yzyang4/scripts/aira_greedy_hce.sbatch
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_matrix_submitted.txt
RUNS=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
touch "$STATE"
TASKS=(spaceship-titanic nomad2018-predict-transparent-conductors)
EXPS=(mlebench/deepseek_greedy_hce_spaceship mlebench/deepseek_greedy_hce_nomad)
ARMS=(full naive consistency)
SEEDS="1 2 3 4 5"
echo "DAEMON_START $(date -u +%FT%TZ) pid=$$"
while :; do
  pending=0
  for ti in 0 1; do
    for a in "${ARMS[@]}"; do
      for s in $SEEDS; do
        combo="${a}|${TASKS[$ti]}|${s}"
        grep -qxF "$combo" "$STATE" && continue
        iss="t1_${a}_${TASKS[$ti]}"
        if ls "$RUNS"/user_yzyang4_issue_${iss}/*seed_${s}_*/checkpoint/journal.jsonl >/dev/null 2>&1; then
          echo "$combo" >> "$STATE"; continue
        fi
        pending=1
        q=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
        [ "$q" -ge 4 ] && continue
        if sbatch --export=ALL,SEED=$s,ARM=$a,EXP=${EXPS[$ti]},ISSUE=$iss "$SB"; then
          echo "$combo" >> "$STATE"
          echo "[$(date -u +%FT%TZ)] submitted $combo ($(wc -l < "$STATE")/30)"
          sleep 5
        else
          echo "[$(date -u +%FT%TZ)] sbatch failed $combo; backoff 60s"; sleep 60
        fi
      done
    done
  done
  [ "$pending" = 0 ] && { echo "DAEMON_DONE all 30 submitted $(date -u +%FT%TZ)"; break; }
  sleep 120
done
