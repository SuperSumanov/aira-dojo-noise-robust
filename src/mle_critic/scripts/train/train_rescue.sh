#!/usr/bin/env bash
# Train a budget-blind rescue model on one prebuilt target-task dose.
# Usage: bash src/mle_critic/scripts/train_rescue.sh nomad|petfinder 500|2000 [seed]
set -euo pipefail
source "$(dirname "$0")/../experiment_env.sh"
TARGET=${1:?expected nomad or petfinder}
K=${2:?expected 500 or 2000}
SEED=${3:-7}
[[ $TARGET == nomad || $TARGET == petfinder ]] || { echo "invalid target" >&2; exit 2; }
[[ $K == 500 || $K == 2000 ]] || { echo "invalid K" >&2; exit 2; }

accelerate launch --config_file "$ACCELERATE_CONFIG" --num_processes 1 "$TRAIN_SCRIPT" \
  --pairs "$DATA_DIR/rescue_${TARGET}_k${K}_rebuilt.jsonl" \
  --cards "$DATA_DIR/cards_current.jsonl" --max-len 2048 \
  --per-device-train-batch-size 1 --per-device-eval-batch-size 1 \
  --gradient-accumulation-steps 16 --learning-rate 1e-5 \
  --num-train-epochs 2 --seed "$SEED" \
  --output-dir "$OUTPUT_DIR/rescue_${TARGET}_k${K}_seed${SEED}"
