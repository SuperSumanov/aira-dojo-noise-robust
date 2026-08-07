#!/usr/bin/env bash
# Budget-blind leave-one-task-out training, matching the reported LOTO protocol.
# Usage: bash src/mle_critic/scripts/train_loto.sh TASK [seed]
set -euo pipefail
source "$(dirname "$0")/../experiment_env.sh"
TASK=${1:?expected an MLEBench task name}
SEED=${2:-7}

deepspeed --num_gpus 1 "$TRAIN_SCRIPT" \
  --pairs "$DATA_DIR/budget_pairs_v2_rebuilt.jsonl" --cards "$DATA_DIR/cards_current.jsonl" \
  --sizes 4000 --max-len 2048 --loto "$TASK" --bs 1 --accum 16 --lr 1e-5 \
  --epochs 2 --seed "$SEED" --deepspeed "$DS_CONFIG"
