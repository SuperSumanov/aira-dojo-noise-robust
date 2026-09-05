#!/usr/bin/env bash
set -euo pipefail
umask 077
archive=/tmp/ds_restore_observer_20260905_6d42547.tar
test "$(sha256sum "$archive" | cut -d' ' -f1)" = f6485105dc3f662ed8a3c71f48e016fabaf1f40ce9c570c790f0085f842075ce
run_dir=$(mktemp -d /tmp/ds-restore-6d42547-XXXXXX)
printf 'DS_RESTORE_DIR=%s\n' "$run_dir"
mkdir "$run_dir/code"
tar -xf "$archive" -C "$run_dir/code"
cd "$run_dir/code"
export PYTHONPATH="$run_dir/code"
export CUDA_VISIBLE_DEVICES=
export HF_HUB_OFFLINE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export DS_RESTORE_CODE_COMMIT=6d425476aff3394f10442befc4d1f7c7bccd4e04
export DS_RESTORE_OUTPUT="$run_dir/source_control_flow.json"
/research/d7/spc/yzyang4/venvs/exp/bin/python -m pytest -q -p no:cacheprovider phase1/tests/test_global_local_ds_completion.py phase1/tests/test_global_local_ds_restore_observer.py > "$run_dir/tests.txt" 2>&1
tail -n 2 "$run_dir/tests.txt"
/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python -m phase1.scripts.validate_ds_restore_source_20260905 > "$run_dir/source.log" 2>&1
tail -n 1 "$run_dir/source.log"
