#!/bin/bash
#SBATCH --job-name=score_sib
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=02:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/score_sib_%j.out
source ~/env_setup.sh
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
cd /research/d7/spc/yzyang4/aira-dojo
/research/d7/spc/yzyang4/venvs/critic/bin/python3 phase1/score_siblings.py   phase1/ckpt_l1_runsplit/N24000 phase1/rm_scores_sibling.json
echo SCORE_SIB_DONE rc=$?
