#!/usr/bin/env bash
# Analyze a tagged 2x2 run. Usage: bash dr_analyze.sh <TAG>
source ~/env_setup.sh 2>/dev/null
TAG="${1:-deepseek-v4-pro}"
CSV=/research/d7/spc/yzyang4/detectreplan/results/t0_2x2_${TAG}.csv
LOG=/research/d7/spc/yzyang4/detectreplan/results/t0_run_${TAG}.log
echo "rows: $(( $(wc -l < "$CSV" 2>/dev/null) - 1 ))"
echo "=== run log tail ==="; tail -n 3 "$LOG" 2>/dev/null
echo "=== analysis ==="
/research/d7/spc/yzyang4/venvs/aira/bin/python /research/d7/spc/yzyang4/detectreplan/analyze_t0.py "$CSV"
