# Component-clean data learning curve formal receipt

This directory is a compact immutable receipt for the formal run at scientific commit
`eb1e1f5847584106b8daba30b75ee5459520c6c4`. The preregistered decision is
`RETROSPECTIVE_DEV_DATA_SCALING_NO_UNLOCK`.

`formal_extract.json` is the compact result and independent-verification extract. `decision_summary.json` and
`decision_curve.csv` are the producer decision artifacts. `verification_1.json` is an independent source-refit receipt.
`ORIGINAL_BUNDLE_SHA256SUMS` is the byte-identical remote manifest. To satisfy the repository's fail-closed staged-filename
credential scan, three harmless receipt filenames were mapped to `runtime_versions.txt` and `credential_shape_scan_{pre,post}.txt`;
`BUNDLE_SHA256SUMS` applies exactly those path substitutions and covers the same bytes.

The original internal `SHA256SUMS` has one deliberately preserved mismatch: `run.log` was still a live `tee` target when
the manifest was written, and the four completion lines were appended afterward. `original_sha256_verify.txt` records the
failure; `posthash_runlog_audit.json` proves that all 37 non-log entries pass, the final log is exactly the expected suffix,
and the audit did not mutate the formal root. This packaging issue does not change the scientific decision and was not
repaired by overwriting or rerunning the formal root.

`packaging_patch_validation/` is a later detached-base overlay validation of the launcher-only correction: 16 focused tests
and all 874 phase1 tests passed, with credential filename/content shape hits of 0/0. These four validation logs are not part
of either earlier bundle manifest; Git records them separately and they do not alter the formal artifacts.
