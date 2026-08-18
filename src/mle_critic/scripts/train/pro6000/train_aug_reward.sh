#!/usr/bin/env bash
# Full-FT L1 run-clean RM. Requires two 96 GB GPU.
# Usage: bash src/mle_critic/scripts/train/pro6000/train_l1_lookahead.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env_augmented_data.sh"
SEED=${1:-6}

#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 2 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--test_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model Qwen/Qwen3-0.6B-Base \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 16 \
#--per-device-eval-batch-size 16 \
#--gradient-accumulation-steps 4 \
#--eval_steps 10 \
#--learning-rate 1e-5 \
#--num-train-epochs 1 \
#--output-dir "$OUTPUT_DIR/Qwen3-0.6B_reward_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen3-0.6B_reward_seed${SEED}.log" 2>&1
#
#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 2 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--test_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model Qwen/Qwen3-1.7B-Base \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 8 \
#--per-device-eval-batch-size 8 \
#--gradient-accumulation-steps 8 \
#--eval_steps 10 \
#--learning-rate 1e-5 \
#--num-train-epochs 1 \
#--output-dir "$OUTPUT_DIR/Qwen3-1.7B_reward_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen3-1.7B_reward_seed${SEED}.log" 2>&1
#
#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 2 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--test_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model Qwen/Qwen3-4B-Base \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 4 \
#--per-device-eval-batch-size 4 \
#--gradient-accumulation-steps 16 \
#--eval_steps 10 \
#--learning-rate 1e-5 \
#--num-train-epochs 1 \
#--output-dir "$OUTPUT_DIR/Qwen3-4B_reward_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen3-4B_reward_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
--test_pairs "$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model Qwen/Qwen3-8B-Base \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 2 \
--per-device-eval-batch-size 2 \
--gradient-accumulation-steps 32 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen3-8B_reward_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-8B_reward_seed${SEED}.log" 2>&1