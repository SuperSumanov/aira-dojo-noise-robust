#!/bin/bash
set +eu
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -euo pipefail
umask 077
root=/research/d7/spc/yzyang4/forets-repair-transfer-20260913-d151en61
if [[ -e "$root/generation.pid" || -e "$root/generation.claim.json" || ! -e "$root/activated.json" ]]; then
    printf 'Existing generation attempt or missing activation; not launching.\n' >&2
    exit 1
fi
if [[ -z "${https_proxy:-${HTTPS_PROXY:-}}" ]]; then
    printf 'Required remote proxy absent.\n' >&2
    exit 1
fi
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
nohup timeout --signal=TERM --kill-after=10s 3300s /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$root/run_repair_transfer_20260913.py" generate > "$root/generation.log" 2>&1 < /dev/null &
set -o noclobber
printf '%s\n' "$!" > "$root/generation.pid"
printf 'Generation worker launched; pid=%s\n' "$!"
