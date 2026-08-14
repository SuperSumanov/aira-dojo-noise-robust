#!/usr/bin/env bash
# Build decision pairs from the current run-grouped Card corpus.
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

AUGMENTED_DATA_DIR=${MLE_CRITIC_AUGMENTED_DATA_DIR:-$REPO_ROOT/data/augmented_mle_critic}
CARDS=$AUGMENTED_DATA_DIR/augmented_cards_current.json
RUNSPLIT=$AUGMENTED_DATA_DIR/runsplit_holdruns.json
RAW_PAIRS=$AUGMENTED_DATA_DIR/decision_pairs_raw.jsonl
FINAL_PAIRS=$AUGMENTED_DATA_DIR/decision_pairs_runsplit.jsonl

python -m src.mle_critic.src.preprocess.download_and_resolve.build_runsplit \
  "$CARDS" "$RUNSPLIT" --seed 7

python -m src.mle_critic.src.preprocess.build_bt_pairs.build_decision_pairs \
  "$RAW_PAIRS" "$CARDS" --budgets 0,1,2

python -m src.mle_critic.src.preprocess.build_bt_pairs.build_runsplit \
  "$CARDS" "$RUNSPLIT" "$RAW_PAIRS" "$FINAL_PAIRS"
