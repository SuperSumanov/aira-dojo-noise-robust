#!/usr/bin/env bash
# Rebuild the aira-dojo venv with a PORTABLE python (uv standalone 3.12) so bin/python works on
# compute nodes too (system python3.12 only exists on the login node -> broken symlink on compute).
set -u
export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export PIP_CACHE_DIR=/research/d7/spc/yzyang4/cache/pip
export TMPDIR=/research/d7/spc/yzyang4/cache/tmp
export UV_CACHE_DIR=/research/d7/spc/yzyang4/cache/uv
export UV_PYTHON_INSTALL_DIR=/research/d7/spc/yzyang4/share/uv/python
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR" "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR"

BIN=/research/d7/spc/yzyang4/bin
mkdir -p "$BIN"
UV="$BIN/uv"

echo "=== install uv (portable) if missing ==="
if [ ! -x "$UV" ]; then
  curl -LsSf https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz -o "$TMPDIR/uv.tgz" \
    && tar xzf "$TMPDIR/uv.tgz" -C "$BIN" --strip-components=1 \
    || { echo "FATAL: uv download failed"; exit 1; }
fi
"$UV" --version || { echo "FATAL: uv not runnable"; exit 1; }

VENV=/research/d7/spc/yzyang4/venvs/aira
AIRA=/research/d7/spc/yzyang4/aira-dojo
MLEBENCH=/research/d7/spc/yzyang4/mle-bench

echo "=== download managed standalone python 3.12 (portable, not system) ==="
"$UV" python install 3.12 || echo "WARN: uv python install non-zero"
echo "=== recreate venv with uv MANAGED python 3.12 (portable across nodes) ==="
rm -rf "$VENV"
"$UV" venv --python-preference only-managed --python 3.12 "$VENV" || { echo "FATAL: uv venv failed"; exit 1; }
PY="$VENV/bin/python"
"$PY" --version
echo "python real path: $(readlink -f "$PY")"

cd "$AIRA" || { echo "FATAL: aira-dojo missing"; exit 1; }
echo "=== uv pip install -r requirements.txt ==="
"$UV" pip install --python "$PY" -r requirements.txt || echo "WARN: requirements non-zero"
echo "=== uv pip install -e aira-dojo (no-deps) ==="
"$UV" pip install --python "$PY" -e . --no-deps || echo "WARN: aira editable non-zero"
echo "=== uv pip install -e mle-bench (no-deps) ==="
"$UV" pip install --python "$PY" --no-deps -e "$MLEBENCH" || echo "WARN: mlebench editable non-zero"

echo "=== import check ==="
"$PY" -c "import dojo, litellm, hydra, omegaconf, pandas, numpy, mlebench; print('aira venv OK; numpy', numpy.__version__)" || echo "WARN: import failed"
echo "AIRA_UV_VENV_DONE"
