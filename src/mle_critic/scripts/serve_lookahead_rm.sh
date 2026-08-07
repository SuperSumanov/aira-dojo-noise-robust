#!/usr/bin/env bash
# Serve a saved L1 RM for the dojo MCTS sidecar protocol.
# Usage: bash src/mle_critic/scripts/serve_lookahead_rm.sh CHECKPOINT_DIR [port]
set -euo pipefail
source "$(dirname "$0")/experiment_env.sh"
export RM_DIR=${1:?expected a checkpoint N<size> directory}
export RM_PORT=${2:-8765}
exec python -m src.mle_critic.src.evaluation.bradley_terry_server
