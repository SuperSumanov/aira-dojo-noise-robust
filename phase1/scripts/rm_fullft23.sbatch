#!/bin/bash
#SBATCH --job-name=rm_ft23
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --cpus-per-task=6
#SBATCH --time=23:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33
#SBATCH --output=/research/d7/spc/yzyang4/logs/rm_ft23_%j.out
# Same recipe as rm_fullft.sbatch (full FT, ZeRO-3, 2 epochs, lr 1e-5) but a 23h wall:
# 24k pairs x 2 epochs = 3000 optimizer steps at ~18.4 s/step = 15.3h, which overruns
# the 12h wall the original template used.
source ~/env_setup.sh
export PATH="/research/d7/spc/yzyang4/venvs/critic/bin:$PATH"
export TRITON_CACHE_DIR=/research/d7/spc/yzyang4/scratch/triton
export TORCH_EXTENSIONS_DIR=/research/d7/spc/yzyang4/scratch/torch_ext
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
PORT=$(( 29000 + (SLURM_JOB_ID % 900) ))
echo "ARGS: ${FT_ARGS}"
deepspeed --master_port $PORT --num_gpus 1 phase1/rm_train_hf.py ${FT_ARGS} \
  --deepspeed phase1/ds_zero3_offload.json --bs 1 --accum 16 --lr 1e-5 --epochs ${EPOCHS:-2} --seed ${SEED:-7}
echo "RM_FULLFT_DONE rc=$?"
