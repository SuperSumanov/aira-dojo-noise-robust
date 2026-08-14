#!/usr/bin/env bash
# Shared setup for the lookahead experiment launchers. Source this file; do not run it directly.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
DATA_DIR=${MLE_CRITIC_DATA_DIR:-$REPO_ROOT/data/mle_critic}
OUTPUT_DIR=${MLE_CRITIC_OUTPUT_DIR:-$REPO_ROOT/outputs/mle_critic}
LOG_DIR=${MLE_CRITIC_LOG_DIR:-$REPO_ROOT/logs/mle_critic}
TRAIN_SCRIPT=$REPO_ROOT/src/mle_critic/src/train/bradley_terry.py
ACCELERATE_CONFIG=$REPO_ROOT/src/mle_critic/recipes/zero3.yaml
# Accelerate launches TRAIN_SCRIPT by file path, so make the repository package
# importable after the training/data/evaluation modules were split into packages.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$OUTPUT_DIR"
cd "$REPO_ROOT"
