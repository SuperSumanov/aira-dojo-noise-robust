#!/usr/bin/env bash
# Submit 8 parallel MCTS T0 jobs (seeds 2..9) via sbatch. Seed 1 already collected.
source ~/env_setup.sh   # sets SLURM_CONF
SB=/research/d7/spc/yzyang4/scripts/aira_mcts_seed.sbatch
for s in "$@"; do
  sbatch --export=ALL,SEED=$s "$SB"
done
echo "=== submitted; current queue ==="
squeue -u yzyang4
