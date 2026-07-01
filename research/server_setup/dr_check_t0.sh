#!/usr/bin/env bash
# Show progress for a tagged 2x2 run. Usage: bash dr_check_t0.sh <TAG> [min_rows] [max_wait_iters]
source ~/env_setup.sh 2>/dev/null
TAG="${1:-deepseek-v4-pro}"
NEED="${2:-5}"
ITERS="${3:-30}"
CSV=/research/d7/spc/yzyang4/detectreplan/results/t0_2x2_${TAG}.csv
LOG=/research/d7/spc/yzyang4/detectreplan/results/t0_run_${TAG}.log
n=0
for i in $(seq 1 "$ITERS"); do
  n=$(( $(wc -l < "$CSV" 2>/dev/null || echo 1) - 1 ))
  [ "$n" -ge "$NEED" ] && break
  sleep 12
done
echo "=== $TAG rows so far: $n ==="
[ -f "$CSV" ] && { head -1 "$CSV"; tail -n +2 "$CSV" | head -12; }
echo "=== log tail ==="; tail -n 4 "$LOG" 2>/dev/null
echo CHECK_DONE
