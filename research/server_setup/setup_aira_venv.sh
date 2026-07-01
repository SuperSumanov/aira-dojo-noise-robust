#!/usr/bin/env bash
# Create a SEPARATE python3.12 venv for aira-dojo host + install it (does NOT touch MLEvolve venv).
# Host is light (no torch; GPU lives in the superimage container).
set -u
export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PIP_CACHE_DIR=/research/d7/spc/yzyang4/cache/pip
export TMPDIR=/research/d7/spc/yzyang4/cache/tmp
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"

VENV=/research/d7/spc/yzyang4/venvs/aira
AIRA=/research/d7/spc/yzyang4/aira-dojo

echo "=== create venv (python3.12, --without-pip + get-pip bootstrap; system lacks python3.12-venv) ==="
rm -rf "$VENV"
/usr/bin/python3.12 -m venv --without-pip "$VENV" || { echo "FATAL: venv create failed"; exit 1; }
PY="$VENV/bin/python"
curl -sS https://bootstrap.pypa.io/get-pip.py -o "$TMPDIR/get-pip.py" && "$PY" "$TMPDIR/get-pip.py" || { echo "FATAL: pip bootstrap failed"; exit 1; }
"$PY" --version
echo "pip ready: $("$PY" -m pip --version)"

cd "$AIRA" || { echo "FATAL: aira-dojo missing at $AIRA"; exit 1; }

echo "=== pip install -r requirements.txt (timeout 2400s) ==="
if timeout 2400 "$PY" -m pip install --prefer-binary -r requirements.txt; then echo "OK requirements"; else echo "WARN: requirements install non-zero"; fi

echo "=== pip install -e . --no-deps ==="
"$PY" -m pip install -e . --no-deps || echo "WARN: editable install non-zero"

echo "=== host import checks (no torch expected on host) ==="
"$PY" -c "import litellm,hydra,omegaconf,pandas,numpy,submitit,kaggle; print('host deps OK; numpy', numpy.__version__, 'litellm', litellm.__version__)" || echo "WARN: host import failed"
"$PY" -c "import dojo; print('dojo import OK')" || echo "WARN: dojo import failed (check src layout / install)"
echo "AIRA_VENV_DONE"
