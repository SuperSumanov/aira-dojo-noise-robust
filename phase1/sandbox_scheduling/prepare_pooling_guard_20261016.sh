#!/bin/bash
set -euo pipefail
umask 077
here=$(cd -- "$(dirname -- "$0")" && pwd)
test ! -e /research/d7/spc/yzyang4/scheduling-pooling-20261016-v2
trap 'result=$?; printf "%s\n" "$result" > "$here/prepare-exit-code.txt"' EXIT
/research/d7/spc/yzyang4/venvs/aira/bin/python -B "$here/pooling_trial_20261015.py" prepare --commit aeb2a48a6d44ce5d0020e7a8e29545c2b5a03b3f
