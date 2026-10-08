#!/bin/bash
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
base=/tmp/r14-evening-20261008.TOHDvG
mkdir "$base/src"
tar -xf "$base/source.tar" -C "$base/src"
cd "$base/src"
printf '%s  %s\n' b6aa47d80728b5dd1c53b44fbe11e8130ec0a67299fde1730b433a33123e1bb2 readiness_qualified_overlap.py 0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd bounded_readiness.py f000c8e017f415ea0d3f1478abac72ba82334d8799cb4ce88cfbbe0364165527 test_readiness_qualified_overlap.py | sha256sum -c -
py=/research/d7/spc/yzyang4/venvs/aira/bin/python
"$py" -B -m unittest test_readiness_qualified_overlap test_neural_overlap_control test_neural_overlap_retry
"$py" -B readiness_qualified_overlap.py qprepare --commit 3f2f98469159bacd01f1193a3b78f38d1e604f51
"$py" -B readiness_qualified_overlap.py qsubmit
