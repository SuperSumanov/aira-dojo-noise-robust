#!/bin/bash
# Only the independently approved10/16 batch; no retry or old-budget reuse.
set -euo pipefail
umask 077
batch_root=/research/d7/spc/yzyang4/scheduling-pooling-20261016-v2
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
test -f "$batch_root/preflight.json"
test -f "$batch_root/production-guard.safe.json"
test ! -e "$batch_root/launch.json"
test ! -e "$batch_root/submit-intent.json"
(set -o noclobber; : > "$batch_root/submit-requested.lock")
trap 'result=$?; printf "%s\n" "$result" > "$batch_root/submit-exit-code.txt"' EXIT
"$python_bin" -B "$(dirname "$0")/pooling_guard_parity_20261016.py" > "$batch_root/guard-parity.safe.json"
"$python_bin" -B "$batch_root/pooling_trial_20261015.py" submit > "$batch_root/submit.private.log" 2>&1
