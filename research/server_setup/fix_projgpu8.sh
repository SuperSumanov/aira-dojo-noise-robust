#!/usr/bin/env bash
# Cancel the two projgpu8-stuck jobs and remove their combos from the state file so the daemon
# resubmits them (now with --exclude=projgpu8).
source ~/env_setup.sh
scancel 6650 6653
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/t1_matrix_submitted.txt
sed -i '/^full|spaceship-titanic|1$/d; /^naive|spaceship-titanic|1$/d' "$STATE"
echo "cancelled 6650 6653; state now $(wc -l < "$STATE")/30:"
echo "=== queue ==="
squeue -u yzyang4
