#!/usr/bin/env bash
MB=/research/d7/spc/yzyang4/mle-bench/mlebench
echo "=== spaceship grade.py ==="
sed -n '1,90p' "$MB/competitions/spaceship-titanic/grade.py"
echo "=== nomad grade.py ==="
sed -n '1,90p' "$MB/competitions/nomad2018-predict-transparent-conductors/grade.py"
echo "=== utils: load_answers / read_csv / prepare_for_metric ==="
grep -n -A 18 -E "def load_answers|def read_csv|def prepare_for_metric" "$MB/utils.py"
echo "=== grade_helpers.py (grader base / InvalidSubmissionError) ==="
sed -n '1,70p' "$MB/grade_helpers.py"
echo RECON_DONE
