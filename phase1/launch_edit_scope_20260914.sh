#!/bin/bash
set +eu
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -euo pipefail
if [[ -z "${https_proxy:-${HTTPS_PROXY:-}}" ]]; then
    printf 'Remote proxy absent; no API or GPU dispatch.\n' >&2
    exit 1
fi
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-edit-scope-stage-20260914-HDeOvQ6i/launch_edit_scope_20260914.py "$@"
