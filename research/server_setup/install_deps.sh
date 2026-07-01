#!/usr/bin/env bash
# Install MLEvolve Python deps into the 'exp' venv (--no-deps), behind CSE proxy.
# Usage:  bash install_deps.sh [core|all|domain]   (default: core = base + ml)
# Re-runnable. Bounded pip sanity + per-file timeout to avoid network/build hangs.
set -u

export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

PY=/research/d7/spc/yzyang4/venvs/exp/bin/python
REPO=/research/d7/spc/yzyang4/MLEvolve

MODE="${1:-core}"
REQS=(requirements_base.txt requirements_ml.txt)
[ "$MODE" = "all" ] && REQS+=(requirements_domain.txt)
[ "$MODE" = "domain" ] && REQS=(requirements_domain.txt)
echo "MODE=$MODE  installing: ${REQS[*]}"

echo "=== precheck ==="
"$PY" --version
"$PY" -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)" 2>/dev/null || echo "torch: not present yet"

echo "=== ensure pip present (uv venvs ship without pip) ==="
"$PY" -m pip --version >/dev/null 2>&1 || "$PY" -m ensurepip --upgrade

echo "=== pip sanity (bounded 60s) ==="
timeout 60 "$PY" -m pip --version || { echo "FATAL: pip not responding within 60s (proxy?). Aborting."; exit 1; }

echo "=== current installed package count ==="
timeout 120 "$PY" -m pip freeze 2>/dev/null | wc -l || echo "freeze timed out"

cd "$REPO" || { echo "FATAL: repo missing at $REPO"; exit 1; }
for req in "${REQS[@]}"; do
  echo "=== install --no-deps --prefer-binary -r $req  (timeout 2400s) ==="
  if timeout 2400 "$PY" -m pip install --no-deps --prefer-binary -r "$req"; then
    echo "OK $req"
  else
    echo "WARN: $req returned non-zero / timed out (continuing)"
  fi
done

echo "=== postcheck: torch ==="
"$PY" -c "import torch; print('torch OK', torch.__version__)" || echo "WARN: torch import failed"

echo "=== key imports ==="
"$PY" - <<'PYEOF'
mods = ["omegaconf","coolname","flask","openai","rich","dataclasses_json","requests",
        "numpy","pandas","sklearn","lightgbm","xgboost","catboost","torch","transformers",
        "sentence_transformers","faiss","tenacity","shutup","kaggle"]
ok, miss = [], []
for m in mods:
    try:
        __import__(m); ok.append(m)
    except Exception as e:
        miss.append(f"{m}({type(e).__name__})")
print("OK  :", ", ".join(ok))
print("MISS:", ", ".join(miss) if miss else "(none)")
PYEOF
echo "INSTALL_SCRIPT_DONE"
