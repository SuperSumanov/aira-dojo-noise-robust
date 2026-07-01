#!/usr/bin/env bash
# Smoke test: tiny end-to-end MLEvolve run on nomad2018 (GPU node).
# Run via:  srun -c 6 -p gpu_2h --qos gpu --account gpu --gres=gpu:1 -C rtx3090 \
#                bash /research/d7/spc/yzyang4/scripts/smoke_run.sh
set -x

source ~/env_setup.sh   # proxy + caches (HF_HOME, TORCH_HOME, ...)

VENV=/research/d7/spc/yzyang4/venvs/exp
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"

REPO=/research/d7/spc/yzyang4/MLEvolve
DATASET=/research/d7/spc/yzyang4/mle-bench-data
EXP_ID=nomad2018-predict-transparent-conductors
SERVER_ID=7

cd "$REPO" || { echo "FATAL: repo missing"; exit 1; }

echo "=== GPU check ==="
nvidia-smi || echo "WARN: nvidia-smi failed (not on a GPU node?)"
"$PY" -c "import torch; print('cuda_available', torch.cuda.is_available())"

echo "=== launch grading (format) server ==="
export DATASET_DIR="$DATASET"
bash launch_server.sh "$SERVER_ID"
export GRADING_SERVER_PORT=$((5005 + SERVER_ID))
for i in $(seq 1 30); do
  if curl -s "http://127.0.0.1:${GRADING_SERVER_PORT}/health" >/dev/null 2>&1; then
    echo "grading server ready on ${GRADING_SERVER_PORT}"; break
  fi
  sleep 1
done

echo "=== run tiny smoke (steps=4, time_limit=1200s, drafts=2, no coldstart, no global memory) ==="
CUDA_VISIBLE_DEVICES=0 "$PY" run.py \
  exp_id="$EXP_ID" \
  dataset_dir="$DATASET" \
  data_dir="$DATASET/$EXP_ID/prepared/public" \
  desc_file="$DATASET/$EXP_ID/prepared/public/description.md" \
  exp_name="$EXP_ID" \
  start_cpu_id=0 \
  cpu_number=6 \
  agent.steps=4 \
  agent.time_limit=1200 \
  agent.initial_drafts=2 \
  coldstart.use_coldstart=False \
  agent.use_global_memory=False
echo "SMOKE_RUN_EXIT=$?"

echo "=== artifacts ==="
ls -lat "$REPO/runs" 2>/dev/null | head -5
LATEST=$(ls -dt "$REPO"/runs/*"$EXP_ID"* 2>/dev/null | head -1)
echo "LATEST_RUN=$LATEST"
if [ -n "$LATEST" ]; then
  echo "--- run dir tree ---"; ls -laR "$LATEST" 2>/dev/null | head -60
  echo "--- journal.json head ---"; head -c 2000 "$LATEST/logs/journal.json" 2>/dev/null || echo "no journal.json yet"
fi
echo "SMOKE_DONE"
