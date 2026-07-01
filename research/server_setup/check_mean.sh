#!/usr/bin/env bash
source ~/env_setup.sh
echo "=== queue ==="; squeue -u yzyang4
echo "=== mean daemon log ==="; tail -n 6 /research/d7/spc/yzyang4/aira-dojo-runs/mean_daemon.log
echo "=== newest t1_hce .out banners (verify lambda=0) ==="
for f in $(ls -t /research/d7/spc/yzyang4/aira-dojo-runs/t1_hce_*.out 2>/dev/null | head -4); do
  echo "--- $(basename "$f") ---"; grep -m1 "T1 HCE arm=" "$f" 2>/dev/null
done
echo CHECK_MEAN_DONE
