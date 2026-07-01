#!/usr/bin/env bash
# Robust per-line installer: install each pinned pkg with --no-deps independently,
# so one bad/source-only package can't abort the whole set (pip -r is atomic).
# Skips the torch/CUDA stack to PRESERVE the working torch 2.11.0+cu128 already in venv.
# Usage: bash install_pkgs_robust.sh [requirements_file]   (default: requirements_ml.txt)
set -u

export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PIP_CACHE_DIR=/research/d7/spc/yzyang4/cache/pip
export TMPDIR=/research/d7/spc/yzyang4/cache/tmp
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"

PY=/research/d7/spc/yzyang4/venvs/exp/bin/python
REQ="${1:-/research/d7/spc/yzyang4/MLEvolve/requirements_ml.txt}"

# Preserve existing torch: skip torch/vision/audio/triton + nvidia-* (incl. the broken nvidia-ml-py3).
SKIP_RE='^(nvidia-|torch==|torchvision|torchaudio|triton==)'

echo "REQ=$REQ"
echo "torch before: $("$PY" -c 'import torch; print(torch.__version__)' 2>/dev/null || echo none)"

ok=0; fail=0; skip=0; failed_pkgs=""
while IFS= read -r line || [ -n "$line" ]; do
  pkg="$(printf '%s' "$line" | sed 's/#.*//' | xargs)"
  [ -z "$pkg" ] && continue
  if printf '%s' "$pkg" | grep -qE "$SKIP_RE"; then
    echo "SKIP $pkg"; skip=$((skip+1)); continue
  fi
  if timeout 600 "$PY" -m pip install --no-deps --prefer-binary "$pkg" >/tmp/pipline.log 2>&1; then
    echo "OK   $pkg"; ok=$((ok+1))
  else
    echo "FAIL $pkg"; tail -2 /tmp/pipline.log | sed 's/^/      /'; fail=$((fail+1)); failed_pkgs="$failed_pkgs $pkg"
  fi
done < "$REQ"

echo "=== summary: ok=$ok fail=$fail skip=$skip ==="
[ -n "$failed_pkgs" ] && echo "FAILED:$failed_pkgs"
echo "torch after: $("$PY" -c 'import torch; print(torch.__version__)' 2>/dev/null || echo none)"
"$PY" - <<'PYEOF'
mods=["sklearn","lightgbm","xgboost","catboost","transformers","sentence_transformers",
      "accelerate","statsmodels","numba","autogluon","tensorflow","datasets","optuna"]
for m in mods:
    try: __import__(m); print("OK  ", m)
    except Exception as e: print("MISS", m, "->", type(e).__name__)
PYEOF
echo "PKGS_ROBUST_DONE"
