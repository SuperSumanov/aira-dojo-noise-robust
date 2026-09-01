# Decision Corpus Evidence Index v10

This package extends the independently verified v9 index without promoting its
provisional first-960 status. It adds four distinct public audit entries:

1. taxonomy-aware archive-disposition persistence;
2. archive-granular retention utility;
3. the append-only 494-to-517 WL snapshot chain; and
4. the identity-erased 14-event rejection-support census.

The support-floor package is deliberately stored under `reconstructions`, not
under distinct `entries`. It points to `archive_granularity_retention`, and the
builder plus a non-importing verifier independently cross-check 19 shared fields
between 0KI and 0KW. Therefore it contributes reproducibility and current-window
lineage, but it does **not** count as a second scientific result.

Formal execution used exact commit
`983bdec9c19da52ca12fd58d6f1a9ae371ea24d5`. Focused/full tests were
`105/1,988 passed` (48 warnings); builder A/B, verifier A/B, input hashes
before/after, file-open tracing, network tracing, and credential scans all
passed. The remote read-only formal root contains 41 files and is bound by
manifest SHA-256 `0c98fde448dee549d6660e3482f9cdfb27f5d21e214c5e04c96162bc0ee55d00`.

An earlier launcher attempt supplied a nonexistent full commit string and
failed with rc=128 before a worktree existed. It produced no index, verifier,
or COMPLETE marker and is retained in `failed_v1_summary.json`.

This is a post-result reporting and claim-accounting artifact. It performs no
new scientific readout and does not establish predictor accuracy, model
scaling, search utility, or method effect. Prospective values, raw senior
archives, and candidate identities were not read; GPU/API/model-fit/base-update
counts are `0/0/0/0`.
