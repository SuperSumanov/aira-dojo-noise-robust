#!/usr/bin/env bash
# Rebuild the four reported rescue datasets from the locally reconstructed L2 pairs.
# Usage: bash src/mle_critic/scripts/build_rescue_datasets.sh
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"

for spec in \
  "nomad nomad2018-predict-transparent-conductors" \
  "petfinder petfinder-pawpularity-score"; do
  read -r SHORT TASK <<<"$spec"
  for K in 500 2000; do
    python -m src.mle_critic.src.dataset.build_rescue_pairs \
      "$DATA_DIR/rescue_${SHORT}_k${K}_local.jsonl" \
      "$DATA_DIR/budget_pairs_v2_rebuilt.jsonl" "$TASK" "$K" --base 4000 --seed 7
  done
done

