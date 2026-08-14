#!/usr/bin/env bash
# Rebuild a byte-exact release from immutable Git LFS batches.
#
# Preferred usage:
#   bash phase1/rebuild_corpus.sh [v6..v11] [output.jsonl] [--overwrite]
# Compatibility usage (latest release):
#   bash phase1/rebuild_corpus.sh output.jsonl
set -euo pipefail

cd "$(dirname "$0")/.."
LATEST=$(tr -d '[:space:]' < phase1/corpus_releases/LATEST)
FIRST="${1:-$LATEST}"
if [[ "$FIRST" == *.jsonl || "$FIRST" == */* ]]; then
  VERSION="$LATEST"
  OUT="$FIRST"
  OVERWRITE="${2:-}"
  echo "NOTICE: treating the first path argument as latest release $LATEST" >&2
else
  VERSION="$FIRST"
  OUT="${2:-phase1/rebuilt/cards_current_${VERSION}.jsonl}"
  OVERWRITE="${3:-}"
fi

RELEASE="phase1/corpus_releases/${VERSION}.json"
[[ -f "$RELEASE" ]] || {
  echo "UNKNOWN or unreproducible corpus release: $VERSION" >&2
  exit 1
}
if [[ -n "$OVERWRITE" && "$OVERWRITE" != "--overwrite" ]]; then
  echo "third argument must be --overwrite when supplied" >&2
  exit 1
fi

if [[ -n "${PY:-}" ]]; then
  PYTHON="$PY"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

ARGS=(
  -m phase1.corpus_release build
  --release "$RELEASE"
  --output "$OUT"
  --receipt "${OUT}.receipt.json"
)
if [[ "$OVERWRITE" == "--overwrite" ]]; then
  ARGS+=(--overwrite)
fi
"$PYTHON" "${ARGS[@]}"
