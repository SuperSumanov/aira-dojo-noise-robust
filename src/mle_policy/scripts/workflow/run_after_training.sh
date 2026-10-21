#!/usr/bin/env bash
set -Eeuo pipefail

# Run the post-training workflow without assuming a fixed number of steps.
# Usage: run_after_training.sh <training-log> <run-root> <output-name> [issue-suffix]
# Example (run from the repository root):
# bash src/mle_policy/scripts/workflow/run_after_training.sh \
#   src/verl/logs/mle_policy/grpo-offline-qwen3_8-27b-thinking-continue-step70-20261017_212344.log \
#   /auxstore/cse/ssd/s1155173938/GRPO-mle-policy-offline/GRPO-offline-Qwen3.8-27B-thinking-continue-step70-bsz124-lr1e-6 \
#   qwen3_8_27b_grpo_20261017_auto_step_final \
#   20261017-auto

REPO=/auxstore/cse/d10/data/s1155173938/aira-dojo-noise-robust
WORKFLOW="$REPO/src/mle_policy/scripts/workflow"
VERL="$REPO/src/verl"
IMAGE=/auxstore/cse/d10/data/s1155173938/singularity_images/verl_vllm.sif
LOG_REL=${1:?training log path is required}
RUN_ROOT=${2:?host checkpoint root is required}
OUTPUT_NAME=${3:?output directory name is required}
ISSUE_SUFFIX=${4:-$(date +%Y%m%d)}
TRAIN_LOG="$REPO/$LOG_REL"
HF_DIR="$REPO/outputs/GRPO-mle-policy-offline/$OUTPUT_NAME"
VLLM_ADAPTER="$HF_DIR/lora_adapter_vllm"
WORK_LOG="$REPO/tmp/workflow_${OUTPUT_NAME}.log"
SERVER_LOG="$REPO/tmp/vllm_${OUTPUT_NAME}.log"
API_KEY=sk-vllm-qwen38-27b-mle-lora

mkdir -p "$REPO/tmp" "$REPO/outputs/GRPO-mle-policy-offline"
exec >>"$WORK_LOG" 2>&1
trap 'echo "[$(date -Is)] FAILED at line $LINENO (exit $?)"' ERR
exec 9>"$WORK_LOG.lock"
flock -n 9 || { echo 'Workflow already running'; exit 1; }
cd "$REPO"
echo "[$(date -Is)] waiting for training completion: $TRAIN_LOG"
FINAL_STEP=$(/usr/bin/python3 "$WORKFLOW/wait_for_training.py" "$TRAIN_LOG" "$RUN_ROOT")
CHECKPOINT="$RUN_ROOT/global_step_${FINAL_STEP}/actor"
echo "[$(date -Is)] final checkpoint: $CHECKPOINT (step $FINAL_STEP)"

if [[ -e "$HF_DIR" ]]; then
  echo "output already exists: $HF_DIR"; exit 1
fi
mkdir -p "$HF_DIR"
singularity exec --nv --cleanenv \
  --env PYTHONUSERBASE="$VERL/verl_env/packages" \
  --env LD_LIBRARY_PATH=/usr/local/cuda/compat:\$LD_LIBRARY_PATH \
  --env PATH=/opt/nodejs/bin:\$PATH \
  -B "$VERL:/workspace/verl" \
  -B /auxstore/cse/d10/data/s1155173938:/auxstore/cse/d10/data/s1155173938 \
  -B /auxstore/cse/d10/data/s1155173938/software/nodejs:/opt/nodejs \
  -B /auxstore/cse/ssd/s1155173938/GRPO-mle-policy-offline:/tmp/GRPO-mle-policy-offline \
  "$IMAGE" bash -lc "cd /workspace/verl && python -m verl.model_merger merge --backend fsdp --local_dir /tmp/GRPO-mle-policy-offline/$(basename "$RUN_ROOT")/global_step_${FINAL_STEP}/actor --target_dir '$HF_DIR'"

singularity exec --cleanenv --env PYTHONUSERBASE="$VERL/verl_env/packages" \
  -B "$REPO:/workspace/repo" "$IMAGE" bash -lc \
  "cd /workspace/repo && PYTHONPATH=/workspace/repo/src/mle_policy python -m src.export.lora_adapter --adapter-dir '$HF_DIR/lora_adapter' --output-dir '$VLLM_ADAPTER'"

if ss -ltn '( sport = :8000 )' | grep -q LISTEN; then
  echo "port 8000 is already in use; refusing to start a duplicate vLLM"; exit 1
fi
setsid nohup env CUDA_VISIBLE_DEVICES=0 singularity exec --nv --cleanenv \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn --env LD_LIBRARY_PATH=/usr/local/cuda/compat:\$LD_LIBRARY_PATH \
  --env VLLM_CACHE_ROOT=/auxstore/cse/d10/data/s1155173938/vllm_cache \
  --env TRITON_HOME=/auxstore/cse/d10/data/s1155173938/triton_home \
  --env TORCH_HOME=/auxstore/cse/d10/data/s1155173938/torchhome \
  --env HF_HOME=/auxstore/cse/d10/data/s1155173938/transformerscache --env HF_HUB_OFFLINE=1 \
  -B /auxstore/cse/d10/data/s1155173938:/auxstore/cse/d10/data/s1155173938 "$IMAGE" \
  vllm serve Qwen/Qwen3.8-27B --served-model-name qwen3.8-27b-base --enable-lora --max-lora-rank 128 \
  --lora-modules qwen3.8-27b-mle-lora="$VLLM_ADAPTER" --host 0.0.0.0 --port 8000 --api-key "$API_KEY" \
  --tensor-parallel-size 1 --max-model-len 131072 --gpu-memory-utilization 0.95 \
  --limit-mm-per-prompt '{"image":0,"video":0}' --max-num-seqs 6 >"$SERVER_LOG" 2>&1 < /dev/null &
server_pid=$!
for _ in $(seq 1 90); do
  if curl -fsS --max-time 5 --noproxy '*' -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/v1/models >/dev/null; then break; fi
  kill -0 "$server_pid" 2>/dev/null || { tail -n 100 "$SERVER_LOG"; exit 1; }
  sleep 10
done
curl -fsS --max-time 10 --noproxy '*' -H "Authorization: Bearer $API_KEY" http://127.0.0.1:8000/v1/models >/dev/null

source /auxstore/cse/d10/data/s1155173938/miniconda3/etc/profile.d/conda.sh
conda activate aira-dojo
set -a; source .env; set +a
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
for task in tensorflow2-question-answering aptos2019-blindness-detection facebook-recruiting-iii-keyword-extraction kuzushiji-recognition; do
  setsid nohup python -m dojo.main_runner_job_array +_exp=mlebench/aira_mcts_qwen_medium_lora \
    "benchmark.tasks=[$task]" \
    'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b-mle-lora' \
    'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b-mle-lora' \
    'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b-mle-lora' \
    'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b-mle-lora' \
    metadata.git_issue_id="${task}-${ISSUE_SUFFIX}" solver.execution_timeout=7200 solver.time_limit_secs=86400 \
    solver.num_children=2 launcher=local_gpu_pool launcher.debug=false 'launcher.devices=[1,2,3]' \
    launcher.max_parallel=3 launcher.gpus_per_task=1 logger.use_wandb=false \
    >"$REPO/tmp/dojo_${task}_${OUTPUT_NAME}.log" 2>&1 < /dev/null &
done
echo "[$(date -Is)] vLLM and four Dojo searches launched"
