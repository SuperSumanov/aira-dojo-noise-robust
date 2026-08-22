# Senior mixed dataset `ac008af` outcome-blind preflight

Verdict: `EXPLORATORY_ONLY_PROTOCOL_AND_REPRODUCIBILITY_BLOCKED`.

This receipt audits only pair metadata and committed training source. It does not open Cards/code/grades,
prospective outcomes, or model outputs; GPU jobs, API calls, and model fits are all zero.

Reproduce with `phase1/audit_senior_mixed_dataset.py` against the four materialized LFS pair objects and the
launcher/training sources at senior commit `ac008af8b907d319b694f26b0ba9cf4053b3bf69`. The focused synthetic
tests pass 3/3. Exact findings and source hashes are in `formal_receipt.json`; the scientific interpretation and
unlock checklist are in `phase1/实验记录/2026-08-23/SeniorMixed_ac008af_结果盲预飞审计.md`.
