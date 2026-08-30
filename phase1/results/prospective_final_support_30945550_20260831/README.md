# Final outcome-blind structural support at `30945550...`

This record freezes the first quiescent post-0829 snapshot for which the
snapshot-delta, transition, batched WL, and exact common-support chains all
promoted to the same immutable snapshot and passed an additional read-only
postflight.

The final structural inventory is 520 physical runs, 494 eligible/first-960
runs, 13,098 endpoints, 3,230 structural pairs, and 34 tasks. The WL update
crossed its pre-registered 12-run batch threshold exactly, adding 12 selected
runs and removing none. The independently reconstructed receipt certifies all
3,230 current structural pairs as the exact canonical common support of the WL
and transition escrow families.

The receipt was produced twice and compared byte-for-byte; its independent
verifier was also run twice and compared byte-for-byte. Separate postflight
checks revalidated both manifests, all stage return codes, forbidden-path and
credential scans, symlink and write-permission gates, and the promoted state
hashes. No prediction pair file or prediction value was opened by the receipt
protocol, and no prospective label, outcome, accuracy, utility, candidate
identity, GPU job, paid API call, or model fit was used.

Claim boundary: this is a positive benchmark-audit and dataset-lineage result.
It is not evidence that either predictor is accurate, that model scaling works,
or that search utility improves. The first-960 cohort remains provisional until
its separately frozen closure receipt exists.

Machine-readable hashes and run counts are in `receipt.json`.
