#!/usr/bin/env bash
# Verify MLEvolve's full import chain + mlebench import (no GPU needed).
# Run after deps install, before the smoke srun, to catch missing deps cheaply.
source ~/env_setup.sh
cd /research/d7/spc/yzyang4/MLEvolve || exit 2
PY=/research/d7/spc/yzyang4/venvs/exp/bin/python

echo "=== import run.py dependency chain ==="
"$PY" -c "import run; print('RUN_IMPORT_OK')"
echo "run_import_rc=$?"

echo "=== import mlebench (grading server deps) ==="
"$PY" -c "from mlebench.grade import validate_submission; from mlebench.registry import registry; print('MLEBENCH_OK')"
echo "mlebench_rc=$?"

echo "IMPORT_CHECK_DONE"
