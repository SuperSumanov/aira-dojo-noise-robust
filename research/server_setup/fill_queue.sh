#!/usr/bin/env bash
# Fill the SLURM queue up to 4 with the next un-submitted T1 combos (state-file tracked, dup-safe).
# QOS allows <=4 jobs in queue, and job arrays are rejected, so we submit in waves: re-run this each
# time slots free up until all 30 are submitted. No persistent process required.
source ~/env_setup.sh
SB=/research/d7/spc/yzyang4/scripts/aira_greedy_hce.sbatch
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_matrix_submitted.txt
RUNS=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
touch "$STATE"
TASKS=(spaceship-titanic nomad2018-predict-transparent-conductors)
EXPS=(mlebench/deepseek_greedy_hce_spaceship mlebench/deepseek_greedy_hce_nomad)
ARMS=(full naive consistency)
SEEDS="1 2 3 4 5"
added=0
for ti in 0 1; do
  for a in "${ARMS[@]}"; do
    for s in $SEEDS; do
      combo="${a}|${TASKS[$ti]}|${s}"
      grep -qxF "$combo" "$STATE" && continue
      iss="t1_${a}_${TASKS[$ti]}"
      if ls "$RUNS"/user_yzyang4_issue_${iss}/*seed_${s}_*/checkpoint/journal.jsonl >/dev/null 2>&1; then
        echo "$combo" >> "$STATE"; continue   # already completed in a prior wave
      fi
      q=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
      if [ "$q" -ge 4 ]; then
        echo "queue full ($q); added $added this wave; progress $(wc -l < "$STATE")/30"
        echo "=== queue ==="; squeue -u yzyang4
        exit 0
      fi
      if sbatch --export=ALL,SEED=$s,ARM=$a,EXP=${EXPS[$ti]},ISSUE=$iss "$SB"; then
        echo "$combo" >> "$STATE"; added=$((added + 1)); echo "submitted $combo"; sleep 3
      else
        echo "sbatch FAILED for $combo (retry next wave)"; sleep 3
      fi
    done
  done
done
echo "ALL_30_SUBMITTED progress=$(wc -l < "$STATE")/30"
echo "=== queue ==="; squeue -u yzyang4
