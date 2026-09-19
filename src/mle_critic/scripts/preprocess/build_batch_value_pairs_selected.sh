#!/usr/bin/env bash
# Build per-batch value pairs for selected tasks, then concatenate them under DIRECTORY.
# A batch is processed only when the path of its batch_cards.json contains one of
# the requested task names; every other batch_cards.json is skipped.
# Usage: bash src/mle_critic/scripts/preprocess/build_batch_value_pairs_selected.sh \
#            DIRECTORY TASK [TASK ...] [--cap N] [--seed N] [--budget-steps N] [--control-depth N]
set -euo pipefail

DIRECTORY=${1:?expected a directory containing batch_cards.json files}
shift

CAP=75
SEED=7
BUDGET_STEPS=-1
CONTROL_DEPTH=999
TASKS=()
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
        --control-depth)
            CONTROL_DEPTH=${2:?expected a value after --control-depth}
            shift 2
            ;;
        --*)
            echo "unknown argument: $1" >&2
            echo "usage: $0 DIRECTORY TASK [TASK ...] [--cap N] [--seed N] [--budget-steps N] [--control-depth N]" >&2
            exit 2
            ;;
        *)
            TASKS+=("$1")
            shift
            ;;
    esac
done

(( ${#TASKS[@]} > 0 )) || { echo "expected at least one task name" >&2; exit 2; }
[[ -d $DIRECTORY ]] || { echo "not a directory: $DIRECTORY" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_critic${PYTHONPATH:+:$PYTHONPATH}"

aggregate_path="$DIRECTORY/batch_value_pairs_selected.jsonl"
aggregate_tmp=$(mktemp "$DIRECTORY/.batch_value_pairs_selected.jsonl.tmp.XXXXXX")
cleanup() {
    rm -f "$aggregate_tmp"
}
trap cleanup EXIT INT TERM

declare -A matched_task=()

found=0
while IFS= read -r -d '' cards_path; do
    selected=0
    for task in "${TASKS[@]}"; do
        if [[ $cards_path == *"$task"* ]]; then
            matched_task["$task"]=1
            selected=1
        fi
    done
    (( selected )) || continue

    found=1
    output_path=$(dirname "$cards_path")/batch_value_pairs.jsonl
    echo "[build_batch_value_pairs_selected] processing $cards_path"
    python -m src.preprocess.build_bt_pairs.build_subtree_pairs \
        "$output_path" \
        "$cards_path" \
        --cap "$CAP" \
        --seed "$SEED" \
        --budget-steps "$BUDGET_STEPS" \
        --control-depth "$CONTROL_DEPTH"
    cat "$output_path" >> "$aggregate_tmp"
done < <(find "$DIRECTORY" -type f -name batch_cards.json -print0 | sort -z)

for task in "${TASKS[@]}"; do
    [[ ${matched_task[$task]+set} ]] || echo "[build_batch_value_pairs_selected] no batch_cards.json matched task $task" >&2
done

if (( ! found )); then
    echo "[build_batch_value_pairs_selected] no batch_cards.json matched the requested tasks under $DIRECTORY" >&2
fi

mv "$aggregate_tmp" "$aggregate_path"
trap - EXIT INT TERM
echo "[build_batch_value_pairs_selected] combined output -> $aggregate_path"
