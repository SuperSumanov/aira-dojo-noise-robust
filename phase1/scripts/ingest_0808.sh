#!/usr/bin/env bash
# Ingest senior batch 0808. Same acceptance protocol as 0806/0807: completeness re-pull,
# extract, REDACT BEFORE READING (his tarballs carry plaintext API keys in
# env_variables.json), build cards, report per-task counts.
set -e
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
R=/research/d7/spc/yzyang4/external/senior_data/mle
A=/research/d7/spc/yzyang4/aira-dojo
D=0808
X=/research/d7/spc/yzyang4/external/senior_data/extract_$D

echo "=== extract $D ==="
rm -rf "$X"; mkdir -p "$X"
for t in "$R/$D"/*.tar.gz; do
  tar -xzf "$t" -C "$X" || echo "TAR_FAIL $t"
done
echo "  journals: $(find "$X" -name journal.jsonl | wc -l)"

echo "=== redact before anything reads it ==="
$P "$A/phase1/tools/redact_secrets.py" "$X" | tail -3

echo "=== build cards ==="
cd "$A"
$P -m phase1.build_cards "$X" phase1/cards_senior_$D.jsonl

echo "=== per-task counts ==="
$P - << EOF
import collections, json
c = collections.Counter(); ids = set()
for l in open("phase1/cards_senior_$D.jsonl"):
    d = json.loads(l); c[d["task"]["name"][:42]] += 1; ids.add(d["id"])
print(f"{sum(c.values())} cards ({len(ids)} unique)")
for t, n in c.most_common():
    print(f"   {t:44s} {n}")
EOF
echo "INGEST_0808_DONE"
