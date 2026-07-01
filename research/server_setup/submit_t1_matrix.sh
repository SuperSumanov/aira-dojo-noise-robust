#!/usr/bin/env bash
# Self-throttling T1-core matrix submitter: 3 arms x TASKS x 5 seeds, <=4 jobs in queue (QOS limit).
# Run via nohup so it survives ssh drops:
#   nohup bash submit_t1_matrix.sh "<task1> <task2> ..." > .../matrix_submit.log 2>&1 &
source ~/env_setup.sh
SB=/research/d7/spc/yzyang4/scripts/aira_greedy_hce.sbatch
TASKS="${1:-spaceship-titanic nomad2018-predict-transparent-conductors}"
ARMS="full naive consistency"
SEEDS="1 2 3 4 5"
exp_for() {
  case "$1" in
    spaceship-titanic) echo mlebench/deepseek_greedy_hce_spaceship ;;
    nomad2018-predict-transparent-conductors) echo mlebench/deepseek_greedy_hce_nomad ;;
    playground-series-s3e18) echo mlebench/deepseek_greedy_hce_s3e18 ;;
    *) echo "UNKNOWN" ;;
  esac
}
n=0
for t in $TASKS; do
  e=$(exp_for "$t")
  if [ "$e" = "UNKNOWN" ]; then echo "skip unknown task $t"; continue; fi
  for a in $ARMS; do
    for s in $SEEDS; do
      iss="t1_${a}_${t}"
      # resumable: skip combos that already produced a journal (re-runnable after a death)
      if ls /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_${iss}/*seed_${s}_*/checkpoint/journal.jsonl >/dev/null 2>&1; then
        echo "[$(date -u +%FT%TZ)] skip (journal exists): $iss seed=$s"; continue
      fi
      while [ "$(squeue -u yzyang4 -h 2>/dev/null | wc -l)" -ge 4 ]; do sleep 60; done
      until sbatch --export=ALL,SEED=$s,ARM=$a,EXP=$e,ISSUE=$iss "$SB"; do
        echo "[$(date -u +%FT%TZ)] sbatch failed (limit race?), retry in 60s"; sleep 60
      done
      n=$((n + 1))
      echo "[$(date -u +%FT%TZ)] submitted #$n: task=$t arm=$a seed=$s issue=$iss exp=$e"
      sleep 5
    done
  done
done
echo "MATRIX_SUBMIT_ALL_DONE total=$n $(date -u +%FT%TZ)"
