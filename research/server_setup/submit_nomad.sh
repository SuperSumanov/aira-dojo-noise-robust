#!/usr/bin/env bash
# Submit nomad2018 MCTS T0 replication jobs (2nd task) via the generalized seed sbatch.
# Usage: bash submit_nomad.sh 1 2 3 4
source ~/env_setup.sh   # sets SLURM_CONF
SB=/research/d7/spc/yzyang4/scripts/aira_mcts_seed.sbatch
for s in "$@"; do
  sbatch --export=ALL,SEED=$s,EXP=mlebench/deepseek_mcts_nomad,ISSUE=deepseek_mcts_t0_nomad "$SB"
done
echo "=== submitted nomad; current queue ==="
squeue -u yzyang4
