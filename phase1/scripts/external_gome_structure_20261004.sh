#!/usr/bin/env bash
set -euo pipefail
source "$HOME/env_setup.sh" >/dev/null 2>&1
exec /research/d7/spc/yzyang4/venvs/aira/bin/python -u -B /research/d7/spc/yzyang4/external_gome_structure_20261004.py
