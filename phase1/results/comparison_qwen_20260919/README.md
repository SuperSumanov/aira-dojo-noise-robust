# 2026-09-19 comparison readout (exploratory)

Read [the findings and limitations](../../COMPARISON_FINDINGS_20260919.md) before using these numbers.
These are reconstructed checkpoint selections, not verified completed final submissions or same-hardware causal effects.

## Files

- `runs.csv` / `runs.json`: one row per configuration, including missing journals; 46 configurations, 43 readable journals.
- `nodes.json`: scoped new-Qwen node structure and numeric fields; no programs, prompts, stdout, raw model responses or environments.
- `summary.json`: within-task/arm descriptive means, medians and sample SD, with explicit coverage.
- `independent.json`: independent list-scan selection and group-statistics verification; shared-seed contrasts and initial-pool inventory. Does not import primary selection code.
- `root_pool_inventory.csv`: 150 candidates from 25 complete structural initial pools. Not an execution manifest or an authorization to run them. Candidate order is creation-time/id, NOT original critic ranking.
- `rank-log-inventory.json`: scoped archive filenames only; no text logs were included. The original per-candidate info-level critic scores cannot currently be mapped from these exports. Does not read environment files.

`original_ranks_available` in the independent result refers only to journal field availability; it does not assert that ranks cannot be recovered from separate logs.
`event_schema` and `logged_best_steps` in the primary readout are empty because uppercase `JOURNAL.jsonl` was deliberately not read. They are not evidence that such logs do not exist.

## Fixed provenance

Remote data root: `/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6`.
Original archives stay quarantined, were not extracted or admitted to production, and may contain private information.
Five-archive private manifest SHA256: `d2e9f41bc697651d266a2574f7b9d4a2d7e474c3851b92d504763e9b535c80cb`.
Structural receipt SHA256: `2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94`.
Historical solver semantics inspected at `be9335348b569086ef9b0af36a15b13e61fec45c`; per-run commits are retained separately.
Primary reader SHA256 at execution: `1b6b0bd9d5cafacb53331d41a743c191da6188f4c7aaad2117d5c4e35892cb7e`.

| File | SHA256 |
|---|---|
| runs.csv | `0c70cf3e07ba7e6f02e5fb37f492efb48341027ac20100487da1cb5dc32dfaf3` |
| runs.json | `040c4463a967a34667dd1943735e923d0193a4f50c4c5eae24e9ada3a2da68c8` |
| nodes.json | `370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9` |
| summary.json | `7abae01493742907a37104bd979b7206439692a1a834ec2f6c0c64359c2d62bc` |
| independent.json | `da5667d1973f678125c26f0186a17bc9775ae7270b49304412cc027038bf092d` |
| root_pool_inventory.csv | `e6bb2f0b632cb2d80d8cf49a1041f90ccf093bb08705558722462faaad9be391` |
| rank-log-inventory.json | `6c2eb42e29a44dc591aa509873e9d999256aa2113893a12e87700c6f18a36c81` |

## Reproduction boundary

Primary reader: `phase1/scripts/read_comparison_qwen_20260919.py`; eight synthetic unit tests in the neighboring test file. The reader is pinned to the remote private receipt and structurally separated snapshot, and refuses changed `LATEST`.
Verifier: `phase1/scripts/verify_comparison_qwen_20260919.py`. It expects `runs.json`, `nodes.json`, `summary.json` and writes new verification/inventory files exclusively. To rerun, copy the three inputs into a new scratch directory; do not overwrite this completed artifact.

Do not extrapolate the exploratory sign tests to equivalence, pool across tasks with incompatible raw score scales, count nodes as independent runs, or reinterpret saved running time as measured total allocation/GPU cost.
