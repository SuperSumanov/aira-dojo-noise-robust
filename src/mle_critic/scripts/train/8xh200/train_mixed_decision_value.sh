#!/usr/bin/env bash
# Full-FT L1 run-clean RM. Requires two 141 GB GPU.
# Usage: bash src/mle_critic/scripts/train/h200/train_mixed_decision_value.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env_augmented_data.sh"
SEED=${1:-7}

#accelerate launch \
#--config_file "$ACCELERATE_CONFIG" \
#--num_processes 8 "$TRAIN_SCRIPT" \
#--train_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
#--test_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
#--cards "$DATA_DIR/augmented_cards_current.json" \
#--model Qwen/Qwen2.5-14B \
#--max-len 16384 \
#--task-cond \
#--per-device-train-batch-size 1 \
#--per-device-eval-batch-size 1 \
#--gradient-accumulation-steps 16 \
#--eval_steps 10 \
#--learning-rate 1e-5 \
#--num-train-epochs 1 \
#--output-dir "$OUTPUT_DIR/Qwen2.5-14B_mixed_decision_value_seed${SEED}" \
#--seed "$SEED" > "$LOG_DIR/Qwen2.5-14B_mixed_decision_value_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 8 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model Qwen/Qwen2.5-7B \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 2 \
--per-device-eval-batch-size 2 \
--gradient-accumulation-steps 8 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen2.5-7B_mixed_decision_value_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-7B_mixed_decision_value_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 8 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model Qwen/Qwen2.5-3B \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 4 \
--per-device-eval-batch-size 4 \
--gradient-accumulation-steps 4 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen2.5-3B_mixed_decision_value_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-3B_mixed_decision_value_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 8 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model Qwen/Qwen2.5-1.5B \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 8 \
--per-device-eval-batch-size 8 \
--gradient-accumulation-steps 2 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen2.5-1.5B_mixed_decision_value_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-1.5B_mixed_decision_value_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 8 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/augmented_cards_current.json" \
--model Qwen/Qwen2.5-0.5B \
--max-len 16384 \
--task-cond \
--per-device-train-batch-size 16 \
--per-device-eval-batch-size 16 \
--gradient-accumulation-steps 1 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 1 \
--output-dir "$OUTPUT_DIR/Qwen2.5-0.5B_mixed_decision_value_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-0.5B_mixed_decision_value_seed${SEED}.log" 2>&1