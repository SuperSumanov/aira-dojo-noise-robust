#!/bin/bash
# ============================================================
#  SLURM 作业脚本模板  ——  CUHK CSE GPGPU-HPC
#  提交： sbatch run_experiment.sbatch
#  查看： squeue -u $USER          取消： scancel <作业号>
#  日志： 实时 tail -f logs/<作业号>.out
# ============================================================

#SBATCH --job-name=exp1                 # 作业名（squeue 里显示）
#SBATCH --partition=gpu_72h             # 队列：gpu_2h调试 / gpu_24h / gpu_72h训练(3天) / batch_168h(7天)
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1                    # 申请几块 GPU，多卡改成 gpu:2 / gpu:4
#SBATCH --cpus-per-task=8               # CPU 核数（数据加载用）
#SBATCH --mem=64G                       # 内存
#SBATCH --time=02:00:00                 # 最长运行时间，别超过队列上限
#SBATCH --output=logs/%j.out           # 标准输出（%j = 作业号）
#SBATCH --error=logs/%j.err            # 报错输出

# ---- 加载你的环境变量（缓存、Token、CUDA 路径等）----
source ~/env_setup.sh

# ---- 激活 Python 环境（按你实际用的改）----
# uv:     source /research/d7/spc/yzyang4/venvs/myenv/bin/activate
# conda:  source ~/miniconda3/bin/activate myenv

# ---- 自检：确认拿到 GPU ----
echo "Job $SLURM_JOB_ID on $(hostname)"
nvidia-smi

# ---- 你的实验命令 ----
cd /research/d7/spc/yzyang4/my_project
python train.py --config configs/exp1.yaml
