#!/bin/bash
# Explicit one-shot postflight; never rerun after any writer has completed.
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
root=/research/d7/spc/yzyang4/scheduling-neural-qualified-overlap-20261008-evening-v1
work=/tmp/r14-evening-20261008.TOHDvG
py=/research/d7/spc/yzyang4/venvs/aira/bin/python
pin=c73cb9ce97ae092ee3bb4ea761201da22dc08d35dfa3f5ecf3aa34bdd8415abc
test -f "$root/closed.json"
test ! -e "$root/readout-v1"
"$py" -B "$root/readiness_qualified_overlap.py" readout
"$py" -B "$root/readiness_qualified_overlap.py" audit --plan-sha "$pin"
"$py" -B "$work/src/evening_supplement.py" --plan-sha "$pin" --output "$work/evening-supplement.json"
sacct -j 17124,17128 -n -P -o JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode
sha256sum "$root/readout-v1/summary.json" "$root/audit-v1/summary.json" "$root/audit-v1/pipeline-contract.json" "$root/runs.csv" "$work/evening-supplement.json"
tar -cf "$work/closed-results.tar" -C "$root" readout-v1/summary.json audit-v1/summary.json audit-v1/pipeline-contract.json runs.csv closed.json launch.json
