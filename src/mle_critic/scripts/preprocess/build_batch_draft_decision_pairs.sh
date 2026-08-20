#!/usr/bin/env bash
# Build per-batch improve decision pairs, then concatenate them under DIRECTORY.
# Usage: bash src/mle_critic/scripts/preprocess/build_batch_improve_decision_pairs.sh DIRECTORY [--cap N] [--seed N] [--budget-steps N]
set -euo pipefail

DIRECTORY=${1:?expected a directory containing batch_cards.json files}
shift

CAP=100
SEED=7
BUDGET_STEPS=0
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

aggregate_path="$DIRECTORY/batch_draft_decision_pairs.jsonl"
aggregate_tmp=$(mktemp "$DIRECTORY/.batch_draft_decision_pairs.jsonl.tmp.XXXXXX")
cleanup() {
    rm -f "$aggregate_tmp"
}
trap cleanup EXIT INT TERM

found=0
while IFS= read -r -d '' cards_path; do
    found=1
    output_path=$(dirname "$cards_path")/batch_draft_decision_pairs.jsonl
    echo "[build_batch_draft_decision_pairs] processing $cards_path"
    python -m src.preprocess.build_bt_pairs.build_augmented_decision_pairs \
        "$output_path" \
        "$cards_path" \
        --cap "$CAP" \
        --seed "$SEED" \
        --budget "$BUDGET_STEPS" \
        --draft_pairs
    cat "$output_path" >> "$aggregate_tmp"
done < <(find "$DIRECTORY" -type f -name batch_cards.json -print0 | sort -z)

if (( ! found )); then
    echo "[build_batch_draft_decision_pairs] no batch_cards.json files found under $DIRECTORY" >&2
fi

mv "$aggregate_tmp" "$aggregate_path"
trap - EXIT INT TERM
echo "[build_batch_draft_decision_pairs] combined output -> $aggregate_path"