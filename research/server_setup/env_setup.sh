#!/bin/bash
# ===============================================================
#  CUHK CSE 服务器环境配置
#  用法：放进 ~/.bashrc 末尾，或存成 ~/env_setup.sh 后用
#        source ~/env_setup.sh 加载
#  存储：/research/d7/spc/yzyang4 (1TB, 到期 2026-09-29)
# ===============================================================

# ---- 资源上限（非 root 提不动就静默跳过，属正常）----
ulimit -n 65536 2>/dev/null || true   # 最大打开文件数
ulimit -u 65536 2>/dev/null || true   # 最大进程数

# ---- 校园代理（linux5 出外网必须走它：pip / huggingface / github 等）----
export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy
# 内网/本机不走代理（SLURM、研究存储等）
export no_proxy=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
export NO_PROXY=$no_proxy

# ---- 大容量存储根目录（所有缓存都放这里，别占家目录配额）----
export DATA=/research/d7/spc/yzyang4

# ---- 把 ~/.cache 和 uv 缓存整体搬到大存储（家目录配额很小，否则装包会爆）----
export XDG_CACHE_HOME=$DATA/cache
export UV_CACHE_DIR=$DATA/cache/uv
export UV_PYTHON_INSTALL_DIR=$DATA/share/uv/python

# ---- 缓存 / 数据目录（全部指向 $DATA）----
export HF_HOME=$DATA/cache/huggingface
export HF_DATASETS_CACHE=$DATA/cache/huggingface/datasets
export TORCH_HOME=$DATA/cache/torch
export TRITON_HOME=$DATA/cache/triton
export PIP_CACHE_DIR=$DATA/cache/pip
export VLLM_CACHE_ROOT=$DATA/cache/vllm
export NLTK_DATA=$DATA/cache/nltk
export CODEX_HOME=$DATA/cache/codex
export SINGULARITY_CACHEDIR=$DATA/cache/singularity/cache
export SINGULARITY_LOCALCACHEDIR=$DATA/cache/singularity/localcache
export SINGULARITY_TMPDIR=$DATA/cache/singularity/tmp

# ---- 密钥 / Token（填你自己的；没有就先留空）----
export HF_TOKEN=                       # huggingface.co/settings/tokens 生成
export WANDB_API_KEY=                  # 已设 offline，可不填
export WANDB_MODE=offline

# ---- OpenAI / Codex / 中转站（用中转站时填这两项）----
export OPENAI_API_KEY=                 # 中转站给你的 key
export OPENAI_API_BASE=                # 中转站的 base url，如 https://xxx.com/v1
export OPENAI_API_TYPE=

# ---- SLURM（集群配置，保留）----
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

# ---- PATH / CUDA（在原 PATH 基础上追加，不覆盖系统路径）----
export PATH=$HOME/bin:$PATH
export PATH=$PATH:/usr/local/cuda-12.8/bin
export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH

# ---- 杂项 ----
export USER=$LOGNAME
export MAIL=/var/spool/mail/$USER
export VLLM_WORKER_MULTIPROC_METHOD=spawn

# ---- 首次使用：自动创建缓存目录 ----
mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TORCH_HOME" "$TRITON_HOME" \
         "$PIP_CACHE_DIR" "$VLLM_CACHE_ROOT" "$NLTK_DATA" "$CODEX_HOME" \
         "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" \
         "$SINGULARITY_CACHEDIR" "$SINGULARITY_LOCALCACHEDIR" "$SINGULARITY_TMPDIR" \
         2>/dev/null
