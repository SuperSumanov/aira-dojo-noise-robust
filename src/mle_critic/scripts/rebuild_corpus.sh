#!/usr/bin/env bash
# Rebuild the merged corpus from per-batch card files (kept out of git: >100MB).
# The manifest is the single source of truth for order and membership.  After
# concatenation, reconstruct and inject physical run IDs for leakage-safe splits.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${1:-$ROOT/data/mle_critic/cards_current.jsonl}"
RAW="$ROOT/data/mle_critic/raw"
MAN="$ROOT/data/mle_critic/raw/corpus_manifest.txt"
TMP="$OUT.raw"

if [ ! -f "$MAN" ]; then
  cat > "$MAN" <<'EOF'
cards_ours_20260727.jsonl
cards_senior_0724.jsonl
cards_senior_0726.jsonl
cards_senior_0727.jsonl
cards_senior_0728.jsonl
cards_senior_0729.jsonl
cards_senior_0730.jsonl
cards_senior_0731.jsonl
cards_senior_0801.jsonl
cards_gen2A.jsonl
cards_gen2B.jsonl
cards_gen2C.jsonl
cards_gen2D.jsonl
cards_gen3A.jsonl
cards_senior_0802.jsonl
cards_t3era_missing.jsonl
cards_senior_0803.jsonl
cards_deepA.jsonl
cards_gen2VAL.jsonl
cards_senior_0804.jsonl
cards_deepB2.jsonl
cards_gen2VALb.jsonl
cards_senior_0805seq.jsonl
cards_senior_0806.jsonl
cards_senior_0807.jsonl
EOF
fi

: > "$TMP"
while read -r name; do
  [ -z "$name" ] && continue
  [ -f "$RAW/$name" ] || { echo "MISSING batch file: $RAW/$name" >&2; exit 1; }
  cat "$RAW/$name" >> "$TMP"
done < "$MAN"

python -m src.mle_critic.src.preprocess.run_segment \
  "$MAN" "$RAW" "$ROOT/data/mle_critic/card_run_map.json"
python -m src.mle_critic.src.preprocess.add_run_id \
  "$TMP" "$OUT" "$ROOT/data/mle_critic/card_run_map.json"
rm -f "$TMP"
echo "rebuilt: $OUT ($(wc -l < "$OUT") cards)"
