#!/bin/bash
# Independent metadata-only probe under user's blanket experiment approval.
# Slurm forbids zero-GPU steps here; reserve one GPU <=180s, do not compute on it.
set -euo pipefail
umask 077
test "${SLURMD_NODENAME:-}" = projgpu12
printf 'job=%s node=%s\n' "$SLURM_JOB_ID" "$SLURMD_NODENAME"
for probe_name in singularity apptainer; do
    probe_path=$(command -v "$probe_name" || true)
    if test -n "$probe_path"; then
        printf 'launcher=%s resolved=%s\n' "$probe_name" "$probe_path"
        readlink -f -- "$probe_path"
        timeout 10s "$probe_path" --version
        sha256sum -- "$probe_path"
    else
        printf 'launcher=%s not_in_path=true\n' "$probe_name"
    fi
done
for probe_path in /usr/bin/singularity /usr/local/bin/singularity /opt/singularity/bin/singularity /usr/bin/apptainer /usr/local/bin/apptainer; do
    if test -x "$probe_path"; then
        printf 'executable=%s\n' "$probe_path"
        readlink -f -- "$probe_path"
        timeout 10s "$probe_path" --version
        sha256sum -- "$probe_path"
    fi
done
printf 'metadata_probe_done=true model_calls=0 task_executions=0\n'
