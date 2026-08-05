#!/usr/bin/env bash
# Rebuild the merged corpus from per-batch card files (kept out of git: >100MB).
# Usage: bash phase1/rebuild_corpus.sh [out.jsonl]
set -e
OUT="${1:-phase1/cards_merged_current.jsonl}"
cd "$(dirname "$0")/.."
cat phase1/cards_ours_20260727.jsonl \
    phase1/cards_senior_0724.jsonl phase1/cards_senior_0726.jsonl phase1/cards_senior_0727.jsonl \
    phase1/cards_senior_0728.jsonl phase1/cards_senior_0729.jsonl phase1/cards_senior_0730.jsonl \
    phase1/cards_senior_0731.jsonl phase1/cards_senior_0801.jsonl \
    phase1/cards_gen2A.jsonl phase1/cards_gen2B.jsonl phase1/cards_gen2C.jsonl phase1/cards_gen2D.jsonl \
    phase1/cards_gen3A.jsonl \
    phase1/cards_senior_0802.jsonl phase1/cards_t3era_missing.jsonl \
    phase1/cards_senior_0803.jsonl phase1/cards_deepA.jsonl phase1/cards_gen2VAL.jsonl \
    phase1/cards_senior_0804.jsonl phase1/cards_deepB2.jsonl phase1/cards_gen2VALb.jsonl > "$OUT"
echo "rebuilt: $OUT ($(wc -l < "$OUT") cards)"
