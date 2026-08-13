#!/usr/bin/env bash
# Rebuild the merged corpus from per-batch card files (kept out of git except via LFS).
# Batch order and membership live in phase1/corpus_manifest.txt -- ONE list, read here and
# by run_segment.py, so the two can no longer drift apart (they did: this script was also
# the file an inline patch once mangled).
#
# Steps: concatenate -> reconstruct physical runs -> inject run_id (release schema v6).
# Usage: bash phase1/rebuild_corpus.sh [out.jsonl]
set -e
OUT="${1:-phase1/cards_merged_current.jsonl}"
cd "$(dirname "$0")/.."
PY="${PY:-/research/d7/spc/yzyang4/venvs/critic/bin/python3}"
MAN=phase1/corpus_manifest.txt

: > "$OUT.raw"
while read -r f; do
  [ -z "$f" ] && continue
  [ -f "phase1/$f" ] || { echo "MISSING batch file: phase1/$f" >&2; exit 1; }
  cat "phase1/$f" >> "$OUT.raw"
done < "$MAN"
echo "concatenated: $(wc -l < "$OUT.raw") cards from $(grep -cve '^$' "$MAN") batch files"

# run reconstruction reads the same manifest; it writes phase1/card_run_map.json
"$PY" -m phase1.run_segment >/dev/null || { echo "run segmentation REJECTED -- corpus left at $OUT.raw" >&2; exit 1; }
"$PY" -m phase1.add_run_id "$OUT.raw" "$OUT"
rm -f "$OUT.raw"
echo "rebuilt: $OUT ($(wc -l < "$OUT") cards, run_id injected)"
