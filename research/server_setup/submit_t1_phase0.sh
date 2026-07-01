#!/usr/bin/env bash
# T1 Phase 0: validate the HCE harness end-to-end — 3 arms x spaceship x seed 1 = 3 runs.
source ~/env_setup.sh
SB=/research/d7/spc/yzyang4/scripts/aira_greedy_hce.sbatch
for ARM in full naive consistency; do
  sbatch --export=ALL,SEED=1,ARM=$ARM,EXP=mlebench/deepseek_greedy_hce_spaceship,ISSUE=t1_p0_$ARM "$SB"
done
echo "=== submitted T1 Phase 0; current queue ==="
squeue -u yzyang4
