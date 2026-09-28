#!/usr/bin/env bash
# Stage 1 of the policy data pipeline: group the LLM calls of every batch.
#
# A batch is the directory that holds a group of run directories -- for
# `raw_journal/<date>/<issue>/<seed>` it is `<issue>`, for
# `comparison/<date>/<task>/<limit>/<model>/<solver>/<seed>` it is `<solver>`.
# It is discovered as the parent of every run directory, so one BATCH_ROOT works
# for both layouts; write `--print` to see what was found and stop.
#
# Prompts are never grouped across batches: a batch is the unit that must share
# one environment (same task, model, hardware, limits).
#
# Each batch is written to OUT_ROOT/batches/<bucket>/<batch>, where <bucket> is
# decided here (not in python) from the model provider:
#   thinking      every run in the batch used a reasoning model
#   non_thinking  every run used a plain completion model
#   other         anything else, including mixed batches
#
# Usage: bash src/mle_policy/scripts/data/build_all_batches.sh BATCH_ROOT OUT_ROOT
set -euo pipefail

BATCH_ROOT=${1:?expected the directory whose immediate subdirectories are batches}
OUT_ROOT=${2:?expected the output root}
PRINT_ONLY=${3:-}

THINKING_PROVIDERS=${THINKING_PROVIDERS:-selfhosted}
NON_THINKING_PROVIDERS=${NON_THINKING_PROVIDERS:-openai}

[[ -d $BATCH_ROOT ]] || { echo "not a directory: $BATCH_ROOT" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_policy${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"

BATCH_ROOT=$(cd "$BATCH_ROOT" && pwd)

# A run directory is the closest ancestor of a journal that owns a dojo_config.
# Its parent is the batch.
mapfile -t batch_dirs < <(python - "$BATCH_ROOT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])


def run_dir(journal):
    for candidate in journal.parents:
        if (candidate / "dojo_config.json").is_file():
            return candidate
    raise SystemExit(f"no dojo_config.json above {journal}")


batches = {run_dir(journal).parent for journal in root.rglob("journal.jsonl")}
print("\n".join(str(batch) for batch in sorted(batches)))
PY
)

if [[ $PRINT_ONLY == --print ]]; then
    printf '%s\n' "${batch_dirs[@]}"
    exit 0
fi

if (( ${#batch_dirs[@]} == 0 )); then
    echo "[build_all_batches] no journals found under $BATCH_ROOT" >&2
    exit 2
fi

mkdir -p "$OUT_ROOT/batches" "$OUT_ROOT/.staging"

classify_batch() {
    # Reads the batch manifest and prints the bucket name.
    python - "$1" "$THINKING_PROVIDERS" "$NON_THINKING_PROVIDERS" <<'PY'
import json
import sys

manifest, thinking, non_thinking = sys.argv[1], set(sys.argv[2].split(",")), set(sys.argv[3].split(","))
providers = set(json.load(open(manifest)).get("providers") or [])
if providers and providers <= thinking:
    print("thinking")
elif providers and providers <= non_thinking:
    print("non_thinking")
else:
    print("other")
PY
}

for batch_dir in "${batch_dirs[@]}"; do
    relative=${batch_dir#"$BATCH_ROOT"/}
    batch_key=${relative//\//__}
    staging="$OUT_ROOT/.staging/$batch_key"
    rm -rf "$staging"

    echo "[build_all_batches] $relative"
    python -m src.data.build_batch_groups \
        --batch-dir "$batch_dir" \
        --batch-key "$batch_key" \
        --output-dir "$staging" > "$staging.log.json" 2>&1 || {
            echo "[build_all_batches] FAILED: $relative (see $staging.log.json)" >&2
            continue
        }

    bucket=$(classify_batch "$staging/manifest.json")
    destination="$OUT_ROOT/batches/$bucket/$batch_key"
    rm -rf "$destination"
    mkdir -p "$(dirname "$destination")"
    mv "$staging" "$destination"
    echo "[build_all_batches]   -> $bucket/$batch_key"
done

rm -rf "$OUT_ROOT/.staging"
echo "[build_all_batches] done; batches under $OUT_ROOT/batches"
