#!/usr/bin/env bash
# Rebuild the merged corpus from per-batch card files (kept out of git: >100MB).
# Usage: bash data/mle_critic/raw/rebuild_corpus.sh [out.jsonl]
set -e
OUT="${1:-data/mle_critic/cards_current.jsonl}"
cat data/mle_critic/raw/cards_ours_20260727.jsonl \
    data/mle_critic/raw/cards_senior_0724.jsonl data/mle_critic/raw/cards_senior_0726.jsonl data/mle_critic/raw/cards_senior_0727.jsonl \
    data/mle_critic/raw/cards_senior_0728.jsonl data/mle_critic/raw/cards_senior_0729.jsonl data/mle_critic/raw/cards_senior_0730.jsonl \
    data/mle_critic/raw/cards_senior_0731.jsonl data/mle_critic/raw/cards_senior_0801.jsonl \
    data/mle_critic/raw/cards_gen2A.jsonl data/mle_critic/raw/cards_gen2B.jsonl data/mle_critic/raw/cards_gen2C.jsonl data/mle_critic/raw/cards_gen2D.jsonl \
    data/mle_critic/raw/cards_gen3A.jsonl \
    data/mle_critic/raw/cards_senior_0802.jsonl data/mle_critic/raw/cards_t3era_missing.jsonl \
    data/mle_critic/raw/cards_senior_0803.jsonl data/mle_critic/raw/cards_deepA.jsonl data/mle_critic/raw/cards_gen2VAL.jsonl \
    data/mle_critic/raw/cards_senior_0804.jsonl data/mle_critic/raw/cards_deepB2.jsonl data/mle_critic/raw/cards_gen2VALb.jsonl \
    data/mle_critic/raw/cards_senior_0805seq.jsonl > "$OUT"
echo "rebuilt: $OUT ($(wc -l < "$OUT") cards)"