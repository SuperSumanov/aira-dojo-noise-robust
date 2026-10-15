#!/bin/bash
# CPU parity then one submission; survives a disconnected monitoring SSH.
set -euo pipefail
umask 077
batch_root=/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
test -f "$batch_root/preflight.json"
test ! -e "$batch_root/launch.json"
test ! -e "$batch_root/submit-intent.json"
(set -o noclobber; : > "$batch_root/submit-requested.lock")
trap 'result=$?; printf "%s\n" "$result" > "$batch_root/submit-exit-code.txt"' EXIT
"$python_bin" -B "$(dirname "$0")/pooling_correction_parity_20261015.py" > "$batch_root/correction-parity.safe.json"
"$python_bin" -B "$batch_root/pooling_trial_20261015.py" submit > "$batch_root/submit.private.log" 2>&1
