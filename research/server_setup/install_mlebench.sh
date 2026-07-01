#!/usr/bin/env bash
# Install mle-bench (editable, --no-deps to protect the pinned env) + import check.
# Run AFTER install_deps.sh core has finished (same venv; no concurrent pip).
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
MLEBENCH=/research/d7/spc/yzyang4/mle-bench

cd "$MLEBENCH" || { echo "FATAL: mle-bench missing at $MLEBENCH"; exit 1; }

echo "=== pip install --no-deps -e mle-bench (timeout 1200s) ==="
if timeout 1200 "$PY" -m pip install --no-deps -e .; then
  echo "OK editable install"
else
  echo "WARN: editable install returned non-zero (continuing to import check)"
fi

echo "=== import check ==="
"$PY" -c "import mlebench; from mlebench.registry import registry; from mlebench.grade import validate_submission; print('mlebench import OK')" || echo "WARN: mlebench import failed (likely a missing dep -- report the traceback)"

echo "=== mlebench CLI ==="
ls -la "$(dirname "$PY")/mlebench" 2>/dev/null || echo "no mlebench entrypoint in venv bin"
"$PY" -m mlebench --help 2>&1 | head -15 || echo "no mlebench CLI module"

echo "MLEBENCH_INSTALL_DONE"
