#!/usr/bin/env bash
set -euo pipefail

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
test_python=/research/d7/spc/yzyang4/venvs/exp/bin/python
test_root=/tmp/codex_task_parent_support_test_20260814
mode=${1:-status}

cd "$repo"
echo "REMOTE_COMMIT $(git rev-parse HEAD)"
echo "REMOTE_STATUS_BEGIN"
git status --short
echo "REMOTE_STATUS_END"

if [[ "$mode" == prepare ]]; then
  mkdir -p "$test_root/phase1/tests"
  : > "$test_root/phase1/__init__.py"
elif [[ "$mode" == test ]]; then
  cd "$test_root"
  PYTHONPATH="$test_root" "$test_python" -m pytest -q \
    phase1/tests/test_task_parent_support_audit.py \
    phase1/tests/test_task_topcenter_rank.py
elif [[ "$mode" == versions ]]; then
  for python_bin in "$test_python" /research/d7/spc/yzyang4/venvs/critic/bin/python; do
    "$python_bin" -c 'import importlib, sys; names=("numpy","scipy","sklearn","torch"); print("PYTHON",sys.executable,sys.version.split()[0]); [print(name, getattr(importlib.import_module(name), "__version__", "unknown")) for name in names]'
  done
elif [[ "$mode" == compile ]]; then
  cd "$test_root"
  PYTHONPATH="$test_root" /research/d7/spc/yzyang4/venvs/critic/bin/python -m py_compile \
    phase1/task_topcenter_rank.py \
    phase1/task_topcenter_engineering_smoke.py \
    phase1/verify_task_topcenter_discovery.py
elif [[ "$mode" != status ]]; then
  echo "unknown mode: $mode" >&2
  exit 2
fi
