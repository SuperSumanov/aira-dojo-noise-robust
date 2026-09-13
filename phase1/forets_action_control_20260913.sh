#!/bin/bash
set +eu
source "$HOME/env_setup.sh" >/dev/null 2>&1
setup_rc=$?
set -euo pipefail
if [[ -z "${https_proxy:-${HTTPS_PROXY:-}}" ]]; then
    printf 'Remote proxy absent; no dispatch (setup rc=%s).\n' "$setup_rc" >&2
    exit 1
fi
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-action-stage-20260913-egtJPLRg/launch_action_prospective_20260913.py "$@"
