#!/bin/bash
#SBATCH --job-name=embed
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --time=04:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/embed_%j.out
source ~/env_setup.sh
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
cd /research/d7/spc/yzyang4/aira-dojo
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
$P phase1/embed_extract.py /research/d7/spc/yzyang4/external/models/qwen2.5-0.5b-instruct    phase1/emb_05b_2048.json --max-len 2048
$P phase1/embed_rank.py phase1/emb_05b_2048.json --dump phase1/embed_scores.json    > phase1/embed_report.txt 2>&1
echo EMBED_DONE rc=$?
