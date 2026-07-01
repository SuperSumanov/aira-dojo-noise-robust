#!/usr/bin/env bash
# aira-dojo baseline smoke: AIRA_GREEDY + DeepSeek + python interpreter (non-container) on spaceship-titanic.
# Run via: srun -c 6 -p gpu_2h --qos gpu --account gpu --gres=gpu:1 -C rtx3090 \
#               bash /research/d7/spc/yzyang4/scripts/aira_smoke.sh
set -x
source ~/env_setup.sh   # proxy (DeepSeek via litellm/httpx) + caches

VENV=/research/d7/spc/yzyang4/venvs/aira
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
AIRA=/research/d7/spc/yzyang4/aira-dojo

cd "$AIRA" || { echo "FATAL: aira-dojo missing"; exit 1; }   # cwd so load_dotenv() finds .env
echo "=== aira-dojo smoke start ==="; date -u +%FT%TZ
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "no nvidia-smi"

SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" -m dojo.main_run +_exp=mlebench/deepseek_smoke logger.use_wandb=False
echo "AIRA_SMOKE_EXIT=$? elapsed_sec=$SECONDS"
date -u +%FT%TZ

echo "=== aira-dojo-runs (LOGGING_DIR) ==="
ls -latR /research/d7/spc/yzyang4/aira-dojo-runs 2>/dev/null | head -40
echo "AIRA_SMOKE_DONE"
