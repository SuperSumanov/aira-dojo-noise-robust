#!/usr/bin/env bash
# Install the tabular ML packages aira-dojo advertises in `available_packages` but that
# aren't in its requirements.txt, so agent-generated code (run in the aira venv via the
# non-container python interpreter) doesn't fail on imports.
# Tabular set only (defer vision/graph: timm, torch-geometric, torchvision).
set -u
export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export UV_CACHE_DIR=/research/d7/spc/yzyang4/cache/uv
export TMPDIR=/research/d7/spc/yzyang4/cache/tmp

UV=/research/d7/spc/yzyang4/bin/uv
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python

echo "=== installing interpreter dep (shutup) + tabular extras (xgboost, statsmodels, bayesian-optimization) ==="
# shutup is imported by aira-dojo's python interpreter child_proc_setup but missing from requirements.txt
"$UV" pip install --python "$PY" shutup xgboost statsmodels bayesian-optimization || echo "WARN: extras install non-zero"

echo "=== import check ==="
"$PY" - <<'PYEOF'
mods = ["xgboost","statsmodels","bayes_opt","lightgbm","sklearn","pandas","numpy","torch"]
for m in mods:
    try:
        __import__(m); print("OK  ", m)
    except Exception as e:
        print("MISS", m, "->", type(e).__name__)
PYEOF
echo "AIRA_EXTRAS_DONE"
