#!/usr/bin/env bash
# Rebuild rescue datasets from the run-clean L2 pairs.
# Usage: bash src/mle_critic/scripts/build_rescue_datasets.sh
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

for spec in \
  "nomad nomad2018-predict-transparent-conductors" \
  "petfinder petfinder-pawpularity-score"; do
  read -r SHORT TASK <<<"$spec"
  for K in 500 2000; do
    python -m src.mle_critic.src.preprocess.build_rescue_pairs \
      "$DATA_DIR/rescue_${SHORT}_k${K}_local.jsonl" \
      "$DATA_DIR/budget_pairs_v3_runsplit.jsonl" "$TASK" "$K" --base 4000 --seed 7
  done
done
