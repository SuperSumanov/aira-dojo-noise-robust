#!/usr/bin/env bash
# Full-FT L1 run-clean RM. Requires two 141 GB GPU.
# Usage: bash src/mle_critic/scripts/train/h200/train_scale_reward.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env_augmented_data.sh"
SEED=${1:-6}

#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 2 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_2000.jsonl" \
#--test_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_2000.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model ../verl_models/Qwen3-14B-Base \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 1 \
#--per-device-eval-batch-size 1 \
#--gradient-accumulation-steps 64 \
#--eval_steps 20 \
#--save_strategy no \
#--learning-rate 1e-5 \
#--num-train-epochs 8 \
#--output-dir "$OUTPUT_DIR/Qwen3-14B_reward_2000_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen3-14B_reward_2000_seed${SEED}.log" 2>&1
#
#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 2 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_4000.jsonl" \
#--test_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_4000.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model ../verl_models/Qwen3-14B-Base \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 1 \
#--per-device-eval-batch-size 1 \
#--gradient-accumulation-steps 64 \
#--eval_steps 20 \
#--save_strategy no \
#--learning-rate 1e-5 \
#--num-train-epochs 4 \
#--output-dir "$OUTPUT_DIR/Qwen3-14B_reward_4000_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen3-14B_reward_4000_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_8000.jsonl" \
--test_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_8000.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model ../verl_models/Qwen3-14B-Base \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 1 \
--per-device-eval-batch-size 1 \
--gradient-accumulation-steps 64 \
--eval_steps 20 \
--save_strategy no \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-14B_reward_8000_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-14B_reward_8000_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_16000.jsonl" \
--test_pairs "$DATA_DIR/experimental/batch_value_pairs_filtered_runsplit_16000.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model ../verl_models/Qwen3-14B-Base \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 1 \
--per-device-eval-batch-size 1 \
--gradient-accumulation-steps 64 \
--eval_steps 20 \
--save_strategy no \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen3-14B_reward_16000_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-14B_reward_16000_seed${SEED}.log" 2>&1