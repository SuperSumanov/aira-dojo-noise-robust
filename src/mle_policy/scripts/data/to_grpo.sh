#!/usr/bin/env bash
# Write GRPO JSONL and Parquet for each split bucket.
# Usage: bash to_grpo.sh OUT_ROOT [BUCKET]
set -euo pipefail

OUT_ROOT=${1:?expected the output root}
BUCKET=${2:-}
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
    [[ -f $dataset/splits.jsonl ]] || { echo "missing splits: $dataset/splits.jsonl" >&2; exit 2; }
    found=1
    echo "[to_grpo] $(basename "$dataset")"
    python -m src.data.to_grpo --dataset "$dataset" --output-dir "$dataset"
done
(( found )) || { echo "no aggregated datasets found under $OUT_ROOT" >&2; exit 2; }
