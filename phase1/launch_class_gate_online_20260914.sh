#!/bin/bash
set +eu
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -euo pipefail
if [[ -z "${https_proxy:-${HTTPS_PROXY:-}}" ]]; then
    printf 'Remote proxy absent; no API or GPU dispatch.\n' >&2
    exit 1
fi
export PYTHONPATH=/research/d7/spc/yzyang4/forets-class-gate-stage-20260914-RWKXbwxc:/research/d7/spc/yzyang4/forets-cheap-v2-stage-20260914-bqkP9eR8
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-class-gate-stage-20260914-RWKXbwxc/launch_class_gate_online_20260914.py "$@"
