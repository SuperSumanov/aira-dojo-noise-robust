#!/usr/bin/env bash
# Stage 1 for journal-level sequence-supervision data.
#
# Usage: bash src/mle_policy/scripts/data/build_all_batches_run_level.sh BATCH_ROOT OUT_ROOT [--print]
set -euo pipefail

BATCH_ROOT=${1:?expected the directory whose immediate subdirectories are batches}
OUT_ROOT=${2:?expected the output root}
PRINT_ONLY=${3:-}

[[ -z $PRINT_ONLY || $PRINT_ONLY == --print ]] || {
    echo "unknown option: $PRINT_ONLY" >&2
    exit 2
}
THINKING_PROVIDERS=${THINKING_PROVIDERS:-selfhosted}
NON_THINKING_PROVIDERS=${NON_THINKING_PROVIDERS:-openai}
[[ -d $BATCH_ROOT ]] || { echo "not a directory: $BATCH_ROOT" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
export PYTHONPATH="$REPO_ROOT/src/mle_policy${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"
BATCH_ROOT=$(cd "$BATCH_ROOT" && pwd)

mapfile -t batch_dirs < <(python - "$BATCH_ROOT" <<'PY'
import sys
from pathlib import Path
from src.data.run_level.big_journal import iter_journal_paths

root = sys.argv[1]


def run_dir(journal):
    for candidate in journal.parents:
        if (candidate / "dojo_config.json").is_file():
            return candidate
    raise SystemExit(f"no dojo_config.json above {journal}")


batches = {run_dir(journal).parent for journal in iter_journal_paths(Path(root))}
print("\n".join(str(batch) for batch in sorted(batches)))
PY
)

if [[ $PRINT_ONLY == --print ]]; then
    printf '%s\n' "${batch_dirs[@]}"
    exit 0
fi
if (( ${#batch_dirs[@]} == 0 )); then
    echo "[build_all_batches_run_level] no journals found under $BATCH_ROOT" >&2
    exit 2
fi

mkdir -p "$OUT_ROOT/batches" "$OUT_ROOT/.staging"

classify_batch() {
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
    echo "[build_all_batches_run_level] $relative"
    python -m src.data.build_batch_groups \
        --batch-dir "$batch_dir" \
        --batch-key "$batch_key" \
        --output-dir "$staging" \
        --run-level > "$staging.log.json" 2>&1 || {
            echo "[build_all_batches_run_level] FAILED: $relative (see $staging.log.json)" >&2
            continue
        }
    bucket=$(classify_batch "$staging/manifest.json")
    destination="$OUT_ROOT/batches/$bucket/$batch_key"
    rm -rf "$destination"
    mkdir -p "$(dirname "$destination")"
    mv "$staging" "$destination"
    echo "[build_all_batches_run_level]   -> $bucket/$batch_key"
done

rm -rf "$OUT_ROOT/.staging"
echo "[build_all_batches_run_level] done; batches under $OUT_ROOT/batches"
