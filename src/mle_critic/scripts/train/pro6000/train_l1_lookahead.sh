#!/usr/bin/env bash
# Full-FT L1 subtree-best RM. Requires two 96 GB GPU.
# Usage: bash src/mle_critic/scripts/train/pro6000/train_l1_lookahead.sh [seed]
set -euo pipefail
source "$(dirname "$0")/../../experiment_env.sh"
SEED=${1:-7}

deepspeed --num_gpus 2 "$TRAIN_SCRIPT" \
  --pairs "$DATA_DIR/value_pairs_v3.jsonl" --cards "$DATA_DIR/cards_current.jsonl" \
  --sizes 24000 --model Qwen/Qwen3-0.6B-Base --max-len 16384 --task-cond --bs 8 --accum 32 \
  --lr 1e-5 --epochs 2 --seed "$SEED" --deepspeed "$DS_CONFIG" \
  > "$LOG_DIR/rm_lookahead_strong_seed${SEED}.log" 2>&1
