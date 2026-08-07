#!/usr/bin/env bash
# Rebuild L1 and L2 pair files from cards. Existing outputs are replaced.
# Usage: bash src/mle_critic/scripts/build_lookahead_datasets.sh
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

python -m src.mle_critic.src.preprocess.build_subtree_pairs \
  "$DATA_DIR/value_pairs_v3_local.jsonl" "$DATA_DIR/cards_current.jsonl" \
  --cap 20000 --seed 7 --split-by tree

python -m src.mle_critic.src.preprocess.build_budget_pairs \
  "$DATA_DIR/budget_pairs_v2_local.jsonl" "$DATA_DIR/budget_flip_v2_local.jsonl" \
  "$DATA_DIR/cards_current.jsonl" --ks 1,2,3,5 --cap 6000 --flip-cap 1200 \
  --tau-filter --tau-quantile 0.9 --flip-boost 5 --seed 7
