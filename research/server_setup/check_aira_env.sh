#!/usr/bin/env bash
# Capability probe for aira-dojo on CSE: container runtime + fakeroot + py3.12/conda/uv.
# Read-only. Run on login node; container runtimes may also/only exist on compute nodes.
source ~/env_setup.sh 2>/dev/null

echo "=== container runtimes ==="
for b in singularity apptainer; do
  if command -v "$b" >/dev/null 2>&1; then
    echo "FOUND $b -> $(command -v "$b")"
    "$b" --version 2>&1 | head -1
  else
    echo "NO $b on PATH"
  fi
done

echo "=== fakeroot / unprivileged build hints ==="
if command -v fakeroot >/dev/null 2>&1; then echo "fakeroot -> $(command -v fakeroot)"; else echo "no fakeroot binary"; fi
grep -E "^(user|group)_namespaces|max_user_namespaces" /etc/subuid /proc/sys/user/max_user_namespaces 2>/dev/null || true
echo "max_user_namespaces: $(cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo unknown)"

echo "=== python 3.12 / conda / uv / mamba ==="
for c in python3.12 conda uv mamba; do
  if command -v "$c" >/dev/null 2>&1; then echo "FOUND $c -> $(command -v "$c")"; "$c" --version 2>&1 | head -1; else echo "NO $c"; fi
done

echo "=== singularity/apptainer cache env (from env_setup) ==="
echo "SINGULARITY_CACHEDIR=${SINGULARITY_CACHEDIR:-unset}"
echo "APPTAINER_CACHEDIR=${APPTAINER_CACHEDIR:-unset}"

echo "=== disk on /research ==="
df -h /research/d7/spc/yzyang4 2>/dev/null | tail -1

echo "CHECK_DONE"
