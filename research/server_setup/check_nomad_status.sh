#!/usr/bin/env bash
source ~/env_setup.sh 2>/dev/null
ISSUE=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_deepseek_mcts_t0_nomad
echo "=== squeue ==="
squeue -u yzyang4
echo "=== seed journals so far ==="
ls "$ISSUE"/*/checkpoint/journal.jsonl 2>/dev/null | wc -l
ls "$ISSUE"/*/checkpoint/journal.jsonl 2>/dev/null
echo "=== recent .out tails (6612-6615) ==="
for j in 6612 6613 6614 6615; do
  f=/research/d7/spc/yzyang4/aira-dojo-runs/mcts_t0_seed_${j}.out
  echo "--- job $j ---"
  tail -n 6 "$f" 2>/dev/null
done
echo "=== POOL (whatever journals exist so far) ==="
bash /research/d7/spc/yzyang4/scripts/pool_t0_r2.sh "$ISSUE"
echo "STATUS_DONE"
