#!/usr/bin/env bash
# Build batch_cards.json in every immediate subdirectory of DIRECTORY.
# Usage: bash src/mle_critic/scripts/preprocess/build_batch_cards.sh DIRECTORY
set -euo pipefail

DIRECTORY=${1:?expected a directory containing run-group directories}
(( $# == 1 )) || { echo "usage: $0 DIRECTORY" >&2; exit 2; }
[[ -d $DIRECTORY ]] || { echo "not a directory: $DIRECTORY" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_critic${PYTHONPATH:+:$PYTHONPATH}"

found=0
while IFS= read -r -d '' run_group_dir; do
    found=1
    echo "[build_batch_cards] processing $run_group_dir"
    python -m src.preprocess.download_and_resolve.build_cards \
        "$run_group_dir" \
        "$run_group_dir/batch_cards.json"
done < <(find "$DIRECTORY" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

if (( ! found )); then
    echo "[build_batch_cards] no subdirectories found under $DIRECTORY" >&2
fi
