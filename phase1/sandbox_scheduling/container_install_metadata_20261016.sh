#!/bin/bash
# Read installation metadata only; no container/model execution or system edits.
set -euo pipefail
test "${SLURMD_NODENAME:-}" = projgpu12
printf 'job=%s node=%s\n' "$SLURM_JOB_ID" "$SLURMD_NODENAME"
whereis -b singularity apptainer || true
dpkg-query -W -f='${Package} ${Version}\n' '*singularity*' '*apptainer*' 2>/dev/null || true
for install_root in /opt /opt1 /usr/local; do
    if test -d "$install_root"; then
        timeout 20s find "$install_root" -maxdepth 5 \( -type f -o -type l \) \( -name singularity -o -name apptainer \) -print 2>/dev/null || true
    fi
done
printf 'installation_metadata_done=true model_calls=0 task_executions=0\n'
