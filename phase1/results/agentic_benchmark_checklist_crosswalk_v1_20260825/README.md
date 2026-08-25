# Agentic Benchmark Checklist crosswalk v1

This directory contains a conservative human crosswalk from the derivative
Decision Corpus + Predictor Benchmark to the Agentic Benchmark Checklist (ABC)
in arXiv:2507.02825v5.

The crosswalk is not a compliance score. It keeps four non-equivalent statuses:

- `PASS_LOCAL`: 9 items;
- `PARTIAL`: 9 items;
- `INHERITED_UPSTREAM`: 5 items;
- `NOT_APPLICABLE`: 1 item.

The upstream paper already assessed MLE-bench. Those upstream findings are
recorded as context and never counted as local passes. In particular, the
do-nothing-agent check is not directly applicable to a predictor benchmark;
an orientation-independent random predictor is the proper analogue, but the
crosswalk deliberately does not relabel that analogue as an ABC pass.

`verify_agentic_benchmark_checklist_crosswalk.py` independently validates the
complete 24-item set, conservative status locks, interpretation contract, and
normalized-LF SHA-256 of 24 local evidence files. It does not fetch external
sources and does not certify that the human semantic assessment is correct.

- `crosswalk.json` SHA-256:
  `fb622cd16e95d6e340ce6fba4bf6661329ec005ec43b184b5ef3cbf29d179b1b`;
- `independent_verification.json` SHA-256:
  `6fadb5c69680f323823050cd4d970066cff4d4e02881381db7317f60d77b174b`;
- verified local evidence files: 24;
- prospective outcomes read / prediction values aggregated / GPU or API calls:
  `false / false / 0`;
- semantic assessment certified / aggregate compliance score reported:
  `false / false`.

The highest-priority unresolved items are real producer environment provenance,
first-960 plus independent closure, publication of the closed immutable corpus,
and the one-time common-support effect analysis after closure.

Reproduce the binding check from the repository root:

```bash
python phase1/verify_agentic_benchmark_checklist_crosswalk.py \
  --repo-root . \
  --crosswalk phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/crosswalk.json \
  --output <fresh-output-path>/independent_verification.json
```
