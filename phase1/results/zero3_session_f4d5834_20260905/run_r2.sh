#!/usr/bin/env bash
set -euo pipefail
umask 077
archive=/tmp/zero3_session_code_20260905_bd1673c.tar
test "$(sha256sum "$archive" | cut -d' ' -f1)" = d592b2b51c92257437a8e1b8b3c243c54a0af21319e5d8c227fb02ce7de7d472
result=$(mktemp -d /tmp/zero3-session-bd1673c-XXXXXX)
printf 'ZERO3_CPU_DIR=%s\n' "$result"
mkdir "$result/code"
tar -xf "$archive" -C "$result/code"
cd "$result/code"
export PYTHONPATH="$result/code"
export CUDA_VISIBLE_DEVICES=
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export ZERO3_CODE_COMMIT=bd1673c83b19b36207b064e18c5d803e3937a819
export ZERO3_CPU_OUTPUT="$result/partition_roundtrip"
/research/d7/spc/yzyang4/venvs/exp/bin/python -m pytest -q -p no:cacheprovider phase1/tests/test_global_local_zero3_session.py phase1/tests/test_global_local_ds_restore_observer.py phase1/tests/test_global_local_critic_session.py phase1/tests/test_zero3_gpu_allocation_gate.py > "$result/tests.txt" 2>&1
tail -n 2 "$result/tests.txt"
/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python -m phase1.scripts.check_zero3_partition_roundtrip_20260905 > "$result/partition.log" 2>&1
tail -n 1 "$result/partition.log"
printf 'ZERO3_CPU_COMPLETE\n'
