#!/usr/bin/env bash
# Rebuild run-clean L1 and L2 pair files from cards. Existing outputs are replaced.
# Usage: bash src/mle_critic/scripts/build_lookahead_datasets.sh
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

python -m src.mle_critic.src.preprocess.build_subtree_pairs \
  /tmp/value_pairs_base.jsonl "$DATA_DIR/cards_current.jsonl" \
  --cap 20000 --seed 7 --split-by tree
python -m src.mle_critic.src.preprocess.build_runsplit \
  "$DATA_DIR/cards_current.jsonl" "$DATA_DIR/card_run_map.json" \
  "$DATA_DIR/runsplit_holdruns.json" "$DATA_DIR" /tmp/value_pairs_base.jsonl \
  --out-name value_pairs_runsplit.jsonl

python -m src.mle_critic.src.preprocess.build_budget_pairs \
  /tmp/budget_pairs_base.jsonl /tmp/budget_flip_base.jsonl \
  "$DATA_DIR/cards_current.jsonl" --ks 1,2,3,5 --cap 6000 --flip-cap 1200 \
  --tau-filter --tau-quantile 0.9 --flip-boost 5 --seed 7
python -m src.mle_critic.src.preprocess.build_runsplit \
  "$DATA_DIR/cards_current.jsonl" "$DATA_DIR/card_run_map.json" \
  "$DATA_DIR/runsplit_holdruns.json" "$DATA_DIR" /tmp/budget_pairs_base.jsonl \
  --out-name budget_pairs_v3_runsplit.jsonl
python -m src.mle_critic.src.preprocess.build_runsplit \
  "$DATA_DIR/cards_current.jsonl" "$DATA_DIR/card_run_map.json" \
  "$DATA_DIR/runsplit_holdruns.json" "$DATA_DIR" /tmp/budget_flip_base.jsonl \
  --out-name budget_flip_v3_runsplit.jsonl
