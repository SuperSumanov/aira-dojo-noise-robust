#!/usr/bin/env bash
# Pilot run on nomad2018: code=v4-pro (config default), feedback=v4-flash.
# Bigger than smoke (steps=20, 30min) to confirm the agent produces working (non-buggy) nodes
# and to measure per-run cost. coldstart/global_memory OFF (isolate the model change vs smoke).
set -x
source ~/env_setup.sh

VENV=/research/d7/spc/yzyang4/venvs/exp
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"
REPO=/research/d7/spc/yzyang4/MLEvolve
DATASET=/research/d7/spc/yzyang4/mle-bench-data
EXP_ID=nomad2018-predict-transparent-conductors
SERVER_ID=8

cd "$REPO" || { echo "FATAL: repo missing"; exit 1; }
echo "=== PILOT start ==="; date -u +%FT%TZ
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

export DATASET_DIR="$DATASET"
bash launch_server.sh "$SERVER_ID"
export GRADING_SERVER_PORT=$((5005 + SERVER_ID))
for i in $(seq 1 60); do
  curl -s "http://127.0.0.1:${GRADING_SERVER_PORT}/health" >/dev/null 2>&1 && { echo "grading server ready"; break; }
  sleep 1
done

SECONDS=0
CUDA_VISIBLE_DEVICES=0 "$PY" run.py \
  exp_id="$EXP_ID" dataset_dir="$DATASET" \
  data_dir="$DATASET/$EXP_ID/prepared/public" \
  desc_file="$DATASET/$EXP_ID/prepared/public/description.md" \
  exp_name="$EXP_ID" start_cpu_id=0 cpu_number=6 \
  agent.steps=20 agent.time_limit=1800 agent.initial_drafts=3 \
  coldstart.use_coldstart=False agent.use_global_memory=False
echo "PILOT_RUN_EXIT=$? elapsed_sec=$SECONDS"
date -u +%FT%TZ

LATEST=$(ls -dt "$REPO"/runs/*"$EXP_ID"* 2>/dev/null | head -1)
echo "LATEST_RUN=$LATEST"
echo "=== node summary ==="
"$PY" - "$LATEST/logs/journal.json" <<'PYEOF'
import json, sys
try:
    j = json.load(open(sys.argv[1])); ns = j.get("nodes", [])
    good = [n for n in ns if n.get("is_buggy") is False]
    print(f"nodes={len(ns)} good_non_buggy={len(good)}")
    for n in ns:
        m = (n.get("metric") or {}).get("value")
        print(f"  {(n.get('id') or '')[:8]} stage={n.get('stage')} buggy={n.get('is_buggy')} metric={m}")
except Exception as e:
    print("summary failed:", e)
PYEOF
echo "PILOT_DONE"
