#!/bin/bash
set +eu
# Login-node catalog access needs the established remote proxy configuration.
# Never print the sourced environment or any credential.
source "$HOME/env_setup.sh" >/dev/null 2>&1
setup_rc=$?
set -euo pipefail
if [[ -z "${https_proxy:-${HTTPS_PROXY:-}}" ]]; then
    printf 'Remote proxy setup absent (setup rc=%s); no network dispatch.\n' "$setup_rc" >&2
    exit 1
fi
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD/launch_forets_reference_20260913.py "$@"
