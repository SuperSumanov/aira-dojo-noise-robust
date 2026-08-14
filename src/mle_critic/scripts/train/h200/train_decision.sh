#!/usr/bin/env bash
# Full-FT L1 run-clean RM. Requires two 140 GB GPU.
# Usage: bash src/mle_critic/scripts/train/h200/train_l1_lookahead.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env.sh"
SEED=${1:-7}

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen3-1.7B-Base \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 8 \
--per-device-eval-batch-size 8 \
--gradient-accumulation-steps 8 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-1.7B-Base_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-1.7B-Base_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen3-4B-Base \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 4 \
--per-device-eval-batch-size 4 \
--gradient-accumulation-steps 16 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-4B-Base_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-4B-Base_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen3-8B-Base \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 2 \
--per-device-eval-batch-size 2 \
--gradient-accumulation-steps 32 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-8B-Base_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-8B-Base_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen3-14B-Base \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 1 \
--per-device-eval-batch-size 1 \
--gradient-accumulation-steps 64 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen3-14B-Base_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen3-14B-Base_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen2.5-1.5B \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 8 \
--per-device-eval-batch-size 8 \
--gradient-accumulation-steps 8 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen2.5-1.5B_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-1.5B_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen2.5-3B \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 4 \
--per-device-eval-batch-size 4 \
--gradient-accumulation-steps 16 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen2.5-3B_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-3B_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen2.5-7B \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 2 \
--per-device-eval-batch-size 2 \
--gradient-accumulation-steps 32 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen2.5-7B_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-7B_critic_decision_seed${SEED}.log" 2>&1

accelerate launch \
--config_file "$ACCELERATE_CONFIG" \
--num_processes 2 "$TRAIN_SCRIPT" \
--train_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--test_pairs "$DATA_DIR/decision_pairs_runsplit.jsonl" \
--cards "$DATA_DIR/cards_current.jsonl" \
--model ../verl_models/Qwen2.5-14B \
--max-len 16384 \
--task-cond \
--budget_cond \
--per-device-train-batch-size 1 \
--per-device-eval-batch-size 1 \
--gradient-accumulation-steps 64 \
--eval_steps 10 \
--learning-rate 1e-5 \
--num-train-epochs 2 \
--output-dir "$OUTPUT_DIR/Qwen2.5-14B_critic_decision_seed${SEED}" \
--seed "$SEED" > "$LOG_DIR/Qwen2.5-14B_critic_decision_seed${SEED}.log" 2>&1