#!/usr/bin/env bash
# Load the user's existing environment before imposing task-specific strictness.
source "$HOME/env_setup.sh" >/dev/null 2>&1
gome_setup_status=$?
if [ "$gome_setup_status" -ne 0 ]; then
    printf '{"stage":"environment_setup_failed","exit_code":%d}\n' "$gome_setup_status"
    exit 3
fi
set -euo pipefail
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -u -B /research/d7/spc/yzyang4/external_gome_structure_20261004.py
