#!/usr/bin/env bash
set -euo pipefail
umask 077
archive=/tmp/critic_session_code_20260905_33ad8ba.tar
test "$(sha256sum "$archive" | cut -d' ' -f1)" = c2eb1c335431c18eac40b09c2aa9677643b78cd667a06ec1d80865650b8f1b7c
run_dir=$(mktemp -d /tmp/critic-session-33ad8ba-XXXXXX)
printf 'CPU_WORK_DIR=%s\n' "$run_dir"
mkdir "$run_dir/code"
tar -xf "$archive" -C "$run_dir/code"
cd "$run_dir/code"
export CUDA_VISIBLE_DEVICES=
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export GLOO_SOCKET_IFNAME=lo
export CRITIC_SESSION_COMMIT=33ad8baca0f23fd54ea4e79c5c23f3c44bbef2ec
export PYTHONPATH="$run_dir/code"
/research/d7/spc/yzyang4/venvs/exp/bin/python -m pytest -q -p no:cacheprovider phase1/tests/test_global_local_critic_consumer.py phase1/tests/test_global_local_critic_session.py > "$run_dir/tests.txt" 2>&1
tail -n 2 "$run_dir/tests.txt"
py=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python
source=/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b
"$py" -m phase1.scripts.validate_critic_session_cpu_20260905 --source-root "$source" --output "$run_dir/a" > "$run_dir/a.log" 2>&1
tail -n 1 "$run_dir/a.log"
"$py" -m phase1.scripts.validate_critic_session_cpu_20260905 --source-root "$source" --output "$run_dir/b" > "$run_dir/b.log" 2>&1
tail -n 1 "$run_dir/b.log"
cmp "$run_dir/a/summary.json" "$run_dir/b/summary.json"
cmp "$run_dir/a/runs.csv" "$run_dir/b/runs.csv"
printf 'CRITIC_SESSION_AB_COMPLETE\n'
