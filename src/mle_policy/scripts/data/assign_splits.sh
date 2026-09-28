#!/usr/bin/env bash
# Assign train/val splits for each aggregated bucket.
# Usage: bash assign_splits.sh OUT_ROOT [SPLIT_BY] [VAL_FRACTION] [BUCKET]
set -euo pipefail

OUT_ROOT=${1:?expected the output root}
SPLIT_BY=${2:-task}
VAL_FRACTION=${3:-0.1}
BUCKET=${4:-}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_policy${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"

if [[ -n $BUCKET ]]; then
    datasets=("$OUT_ROOT/$BUCKET")
else
    datasets=("$OUT_ROOT"/*)
fi

found=0
for dataset in "${datasets[@]}"; do
    [[ -f $dataset/manifest.json && -f $dataset/groups.jsonl ]] || continue
    found=1
    echo "[assign_splits] $(basename "$dataset")"
    python -m src.data.assign_splits --dataset "$dataset" --split-by "$SPLIT_BY" --val-fraction "$VAL_FRACTION"
done
(( found )) || { echo "no aggregated datasets found under $OUT_ROOT" >&2; exit 2; }
