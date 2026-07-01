#!/usr/bin/env bash
# Wait up to ~4 min for the HCE eval path to actually fire on a valid node ("HCE arm=" log),
# or for the run process to die (DONE rc=1). Agent-code tracebacks (buggy drafts) are NORMAL and
# are NOT treated as failures.
source ~/env_setup.sh 2>/dev/null
f=""
for i in $(seq 1 24); do
  f=$(ls -t /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_*.out 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    if grep -q "HCE arm=" "$f"; then
      echo "=== HCE EVAL FIRED — harness end-to-end OK ==="
      grep "HCE arm=" "$f" | tail -6
      echo "VERDICT=OK"; exit 0
    fi
    if grep -qE "_DONE rc=1" "$f"; then
      echo "=== run process exited rc=1 — inspecting tail ==="
      tail -n 30 "$f"
      echo "VERDICT=FAIL"; exit 0
    fi
  fi
  sleep 10
done
echo "=== no valid node yet (drafts still iterating); run still alive ==="
squeue -u yzyang4
[ -n "$f" ] && { echo "--- newest out tail ---"; tail -n 6 "$f"; }
echo "VERDICT=PENDING"
