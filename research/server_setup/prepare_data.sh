#!/usr/bin/env bash
# Prepare one mle-bench competition's data into /research mle-bench-data.
# Requires: ~/.kaggle/kaggle.json (with "proxy" field) + competition rules accepted on Kaggle.
# Usage: bash prepare_data.sh [competition-id]   (default: nomad2018-predict-transparent-conductors)
set -u

export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk

VENV=/research/d7/spc/yzyang4/venvs/exp
COMP="${1:-nomad2018-predict-transparent-conductors}"
DATADIR=/research/d7/spc/yzyang4/mle-bench-data

echo "=== preparing $COMP -> $DATADIR ==="
# stdin from /dev/null: if rules are NOT accepted, kaggle's y/n prompt gets EOF and fails fast
# instead of hanging forever.
"$VENV/bin/mlebench" prepare -c "$COMP" --data-dir "$DATADIR" < /dev/null
echo "PREPARE_EXIT=$?"

echo "=== prepared/public listing ==="
ls -la "$DATADIR/$COMP/prepared/public" 2>/dev/null || echo "NO prepared/public (prepare likely failed)"
echo "PREPARE_DONE"
