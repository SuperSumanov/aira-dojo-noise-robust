#!/usr/bin/env bash
# Budget-blind leave-one-task-out training, matching the reported LOTO protocol.
# Usage: bash src/mle_critic/scripts/train_loto.sh TASK [seed]
set -euo pipefail
source "$(dirname "$0")/../experiment_env.sh"
TASK=${1:?expected an MLEBench task name}
SEED=${2:-7}

accelerate launch --config_file "$ACCELERATE_CONFIG" --num_processes 1 "$TRAIN_SCRIPT" \
  --pairs "$DATA_DIR/budget_pairs_v3_runsplit.jsonl" --cards "$DATA_DIR/cards_current.jsonl" \
  --max-len 2048 --loto "$TASK" \
  --per-device-train-batch-size 1 --per-device-eval-batch-size 1 \
  --gradient-accumulation-steps 16 --learning-rate 1e-5 \
  --num-train-epochs 2 --seed "$SEED" \
  --output-dir "$OUTPUT_DIR/loto_${TASK}_seed${SEED}"
