#!/usr/bin/env bash
# Train one L2 arm. "conditioned" appends K near the scalar pooling token; "blind" omits K.
# Usage: bash src/mle_critic/scripts/train_l2_budget.sh blind|conditioned [seed]
set -euo pipefail
source "$(dirname "$0")/../experiment_env.sh"
ARM=${1:?expected blind or conditioned}
SEED=${2:-7}
EXTRA=()
case "$ARM" in
  blind) ;;
  conditioned) EXTRA+=(--budget-cond --budget-pos tail) ;;
  *) echo "unknown arm: $ARM" >&2; exit 2 ;;
esac

accelerate launch --config_file "$ACCELERATE_CONFIG" --num_processes 1 "$TRAIN_SCRIPT" \
  --pairs "$DATA_DIR/budget_pairs_v2_rebuilt.jsonl" \
  --cards "$DATA_DIR/cards_current.jsonl" --sizes 8000 --max-len 2048 \
  --per-device-train-batch-size 1 --per-device-eval-batch-size 1 \
  --gradient-accumulation-steps 16 --learning-rate 1e-5 --num-train-epochs 2 --seed "$SEED" \
  "${EXTRA[@]}"
