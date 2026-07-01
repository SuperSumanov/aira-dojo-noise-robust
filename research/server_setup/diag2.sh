#!/usr/bin/env bash
source ~/env_setup.sh
echo "=== sacct (jobs 6650-6658) ==="
sacct -j 6650,6651,6652,6653,6654,6655,6656,6657,6658 --format=JobID,State,Elapsed,NodeList%12,ExitCode 2>/dev/null | grep -vE "\.batch|\.extern|\.0 "
echo "=== 6650 (projgpu8) tail ==="; tail -n 6 /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_6650.out 2>/dev/null
echo "=== 6653 (projgpu8) tail ==="; tail -n 6 /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_6653.out 2>/dev/null
echo "=== 6654 tail ==="; tail -n 4 /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_6654.out 2>/dev/null
echo "=== journal node counts (full + consistency running) ==="
for iss in t1_full_spaceship-titanic t1_consistency_spaceship-titanic; do
  for d in /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_${iss}/*/checkpoint/journal.jsonl; do
    [ -f "$d" ] && echo "$(wc -l < "$d") nodes : $(echo "$d" | grep -oE 'seed_[0-9]+')"
  done
done
echo "DIAG2_DONE"
