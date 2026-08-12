#!/usr/bin/env bash
# Rebuild the v9 decision-pair training and frozen evaluation files.
# Usage: bash src/mle_critic/scripts/build_decision_datasets.sh
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

RAW_PAIRS="$DATA_DIR/decision_pairs_v9raw.jsonl"

python -m src.mle_critic.src.preprocess.build_decision_pairs \
  "$RAW_PAIRS" "$DATA_DIR/cards_current_v9.jsonl" \
  --orientation "$DATA_DIR/task_orientation.json" --ks 0,1,2

python -m src.mle_critic.src.preprocess.build_runsplit \
  "$DATA_DIR/cards_current_v9.jsonl" "$DATA_DIR/card_run_map.json" \
  "$DATA_DIR/runsplit_holdruns.json" "$DATA_DIR" "$RAW_PAIRS" \
  --out-name decision_pairs_runsplit.jsonl

python -m src.mle_critic.src.preprocess.build_decision_clean \
  "$DATA_DIR/decision_pairs_runsplit.jsonl" "$DATA_DIR" \
  --budgets 0,1,2 --write-frozen-test
