#!/usr/bin/env bash
# Submit the T1 30-run job array (SLURM manages the <=4 concurrency via %4).
source ~/env_setup.sh
sbatch /research/d7/spc/yzyang4/scripts/aira_greedy_hce_array.sbatch
echo "=== queue ==="
squeue -u yzyang4
