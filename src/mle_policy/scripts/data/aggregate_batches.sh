#!/usr/bin/env bash
# Merge each bucket of built batches into <out>/<bucket>/.
# Usage: bash aggregate_batches.sh OUT_ROOT [BUCKET]
set -euo pipefail

OUT_ROOT=${1:?expected the output root used by build_all_batches.sh}
BUCKET=${2:-}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_policy${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"

if [[ -n $BUCKET ]]; then
    bucket_dirs=("$OUT_ROOT/batches/$BUCKET")
else
    bucket_dirs=("$OUT_ROOT"/batches/*)
fi

found=0
for bucket_dir in "${bucket_dirs[@]}"; do
    [[ -d $bucket_dir ]] || continue
    compgen -G "$bucket_dir/*/manifest.json" > /dev/null || continue
    found=1
    bucket=$(basename "$bucket_dir")
    echo "[aggregate_batches] $bucket"
    python -m src.data.aggregate_groups --input "$bucket_dir" --output-dir "$OUT_ROOT/$bucket"
done
(( found )) || { echo "no built batches found under $OUT_ROOT/batches" >&2; exit 2; }
