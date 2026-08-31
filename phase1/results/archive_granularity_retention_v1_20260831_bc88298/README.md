# Archive Granularity Retention Audit v1

This directory records the formal, outcome-blind full-census accounting run for
`archive_granularity_retention_audit_v1`.

- Exact scientific commit: `bc88298cb410183cf642c132c5d1df2e2d9497ba`
- Formal root: `/research/d7/spc/yzyang4/prospective-archive-retention/formal-bc88298-v1`
- Frozen snapshot: `30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f`
- Frozen observations: `dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`
- Formal status: `ARCHIVE_GRANULARITY_RETENTION_STRONG`
- Independent verification: `INDEPENDENT_ARCHIVE_GRANULARITY_RETENTION_PASS`
- Focused/full tests: `10/1860 passed` (`48` full-suite warnings)
- Result SHA-256: `f28ef79447ded3d642c563cf1a684f86f063a9e0c270949f5f935f995c9a2184`
- Verification SHA-256: `4965c04739d6ca8468be7fa04f807a8f5c123b3ce2adec37efbfd47608d3b187`
- Manifest SHA-256: `5a5f5168ac625d43d8f4136c6c4b556d8820a300fbf46eaa99a1b70917957823`

All six affected competitions retained eligible accepted support. Archive-granular
validation retained 20 accepted archives, 94 physical runs, 92 eligible runs and
2,558 eligible endpoints that a task-level blacklist would additionally discard.
Those eligible units are 18.6235% of accepted runs and 19.5297% of accepted
endpoints. Dominant-task shares were 31.5217% and 36.9038%, below the frozen 70%
strong-gate limits.

The two producer outputs and two independent-verifier outputs are byte-identical.
The postflight rechecked the complete manifest, exact commit, clean worktree,
read-only/symlink gates, access traces and all aggregate fields. Network,
forbidden-path, credential and identity hits were all zero.

This is deterministic corpus accounting, not an observed method effect. It does
not estimate predictor accuracy, scaling or search utility, and it does not
support task whitelisting/blacklisting or future-corpus stationarity. Archive
payloads, labels, outcomes, prediction values, accuracy, utility and affected
identities were not read or emitted; GPU/API/model-fit/base-update usage was
`0/0/0/0`.
