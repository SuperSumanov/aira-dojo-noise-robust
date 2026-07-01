#!/usr/bin/env bash
source ~/env_setup.sh 2>/dev/null
for j in 6645 6646 6647 6648; do
  echo "=== job $j ==="
  tail -n 6 /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_${j}.out 2>/dev/null || echo "(no out)"
done
echo "=== spaceship-full issue dir subdirs ==="
ls -d /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_t1_full_spaceship-titanic/*/ 2>/dev/null
echo "=== journals + node counts ==="
for d in /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_t1_full_spaceship-titanic/*/checkpoint/journal.jsonl; do
  [ -f "$d" ] && echo "$(wc -l < "$d") nodes : $d"
done
echo "DIAG_DONE"
