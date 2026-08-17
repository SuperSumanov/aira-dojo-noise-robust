#!/usr/bin/env bash
# Build batch_value_pairs.jsonl beside every batch_cards.json under DIRECTORY.
# Usage: bash src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh DIRECTORY [--cap N] [--seed N] [--budget-steps N]
set -euo pipefail

DIRECTORY=${1:?expected a directory containing batch_cards.json files}
shift

CAP=100
SEED=7
BUDGET_STEPS=-1
while (( $# )); do
    case $1 in
        --cap)
            CAP=${2:?expected a value after --cap}
            shift 2
            ;;
        --seed)
            SEED=${2:?expected a value after --seed}
            shift 2
            ;;
        --budget-steps)
            BUDGET_STEPS=${2:?expected a value after --budget-steps}
            shift 2
            ;;
        *)
            echo "unknown argument: $1" >&2
            echo "usage: $0 DIRECTORY [--cap N] [--seed N] [--budget-steps N]" >&2
            exit 2
            ;;
    esac
done

[[ -d $DIRECTORY ]] || { echo "not a directory: $DIRECTORY" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_critic${PYTHONPATH:+:$PYTHONPATH}"

found=0
while IFS= read -r -d '' cards_path; do
    found=1
    output_path=$(dirname "$cards_path")/batch_value_pairs.jsonl
    echo "[build_batch_value_pairs] processing $cards_path"
    python -m src.preprocess.build_bt_pairs.build_subtree_pairs \
        "$output_path" \
        "$cards_path" \
        --cap "$CAP" \
        --seed "$SEED" \
        --budget-steps "$BUDGET_STEPS"
done < <(find "$DIRECTORY" -type f -name batch_cards.json -print0 | sort -z)

if (( ! found )); then
    echo "[build_batch_value_pairs] no batch_cards.json files found under $DIRECTORY" >&2
fi
