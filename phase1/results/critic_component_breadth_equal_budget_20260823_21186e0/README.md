# Equal-pair-budget component breadth formal receipt

This directory is the compact immutable receipt for the formal run at scientific commit
`21186e036b41b35c087fd3cb02e99a88b241a4ed`. The preregistered decision is
`RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK`.

`formal_extract.json` contains the compact decision and independent source-refit verification. `decision_summary.json` and
`decision_arm_metrics.csv` are the producer decision artifacts; `verification_1.json` is the independent receipt.
`ORIGINAL_BUNDLE_SHA256SUMS` is the byte-identical remote bundle manifest. The repository's fail-closed staged-filename scan
requires three harmless path mappings to `runtime_versions.txt` and `credential_shape_scan_{pre,post}.txt`;
`BUNDLE_SHA256SUMS` covers the same bytes under those repository-safe names.

The original internal `SHA256SUMS` deliberately preserves one mismatch: `run.log` was a live `tee` target, so its completion
suffix arrived after the manifest. `original_sha256_verify.txt` records that mismatch, while `posthash_runlog_audit.json`
verifies all 39 non-log entries, the exact final suffix, and no audit mutation of the formal root. The launcher-only packaging
correction was already validated by the shared 16-focused/874-full overlay receipt in the companion data-curve result.
