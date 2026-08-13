#!/usr/bin/env bash
# Full-FT L1 run-clean RM. Requires two 96 GB GPU.
# Usage: bash src/mle_critic/scripts/train/pro6000/train_l1_lookahead.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env.sh"
SEED=${1:-7}

accelerate launch \
--config_file "$ACCELERATE_ZERO2_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model Qwen/Qwen3-1.7B-Base \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 8 \
--per-device-eval-batch-size 8 \
--gradient-accumulation-steps 8 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-1.7B-Base_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-1.7B-Base_critic_decision_seed${SEED}.log" 2>&1