#!/usr/bin/env bash
# Does setuid singularity RUN a container WITHOUT user namespaces? (build is already known blocked)
# If this works, "build .sif externally -> copy -> run here" is a viable path.
source ~/env_setup.sh 2>/dev/null
echo "host: $(hostname)"
echo "singularity: $(command -v singularity) | $(singularity --version 2>&1 | head -1)"
echo "userns(max_user_namespaces): $(cat /proc/sys/user/max_user_namespaces 2>/dev/null)"
echo "=== try: singularity exec docker://busybox echo (pull+run, unprivileged) ==="
timeout 200 singularity exec docker://busybox echo SINGULARITY_RUN_OK
echo "run_rc=$?"
echo "SINGULARITY_TEST_DONE"
