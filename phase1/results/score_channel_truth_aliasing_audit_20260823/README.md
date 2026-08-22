# Score-channel truth aliasing audit

This directory contains aggregate-only evidence from the old 158-parent cohort. The protocol and implementation were
frozen and pushed at commit `5e3ebcd571676cd55188bf22ad7265b34b7dc1b8` before raw-grade aggregates were read.

- `analysis.json`: deterministic producer output; SHA-256
  `38788c89ca8231428482d9bea1a43e5a641eda7a6efa26dec89eb6499e594ba5`.
- `verification.json`: independent reconstruction; SHA-256
  `4b56b9e2e3cb9c52f390dd92b3877f818ef7b2edecc27cde919c06a09fb22789`.
- `focused_tests.stdout`: exact-commit focused-test receipt (5/5).
- `resource_receipt.txt`: CPU-only resource declaration.
- `future_truth_open_count.txt`: forbidden future-vault/syscall count (0).
- `filename_scan_count.txt` and `content_scan_count.txt`: credential scans (0/0).

The result is `MATERIAL_Y_NORM_ALIASING`: 147 parents across 16 tasks are tied after `y_norm` clipping but distinct on
official five-decimal `graded`. This does not reverse the old primary verdict and does not authorize replay, GPU work,
or an effect claim. It only activates the pre-frozen permission to add a separately named raw-grade support estimand
before the future truth vault is opened.
