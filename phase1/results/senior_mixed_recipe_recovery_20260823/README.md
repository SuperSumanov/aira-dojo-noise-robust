# Senior `ac008af` mixed-recipe recovery

Formal status: `UNIQUE_IN_FROZEN_GRID_AND_BYTE_EXACT`.

The previously unrecorded generation recipe for
`decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl` was recovered retrospectively.  The frozen
search contained exactly 66 candidates: all six input orders, seed 7, 15,000 requested samples, 1,500 decision
samples, and global-value counts from 0 through 7,500 in increments of 750.  Exactly one candidate matched all
15,875 parsed records in order:

- datasets: batch value, decision, hardware/time global value;
- weights: `8 1 1` (sample counts `12000 1500 1500`);
- retained test split: decision;
- seed: 7.

Independent serialization reproduced 6,625,497 bytes with SHA-256
`7792a7da4119bb607cf76628fcdde19923898651ac734ff6afffb0732883cf6e`.  Separately, the original builder at
senior commit `ac008af8b907d319b694f26b0ba9cf4053b3bf69` was run twice on Linux; both runs produced the same row
count, byte size, and SHA-256 and were byte-identical to each other.

This is a bounded retrospective recovery, not evidence that the command was recorded when the artifact was
created, and not a model-effect result.  It removes only the “recipe cannot be reconstructed” blocker.  Frozen-test
reuse, incomplete physical-experiment provenance, Cards LFS 404, launcher filename mismatch, and the
prompt/mixture/offload confound remain unresolved; no GPU job, API call, or model fit was performed.

The machine-readable evidence is `formal_receipt.json`; `remote_verification.json` records the independent Linux
builder double run and a second two-run audit under Python 3.11.15.  The Windows 3.13.4 and Linux receipts have the
same scientific-core SHA-256 even though their runtime fields differ.  Reproduce the search with
`phase1/recover_senior_mixed_recipe.py` and the four locked LFS objects plus the locked upstream builder source.
