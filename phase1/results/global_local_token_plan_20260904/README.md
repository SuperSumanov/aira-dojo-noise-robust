# Historical global→local token-plan receipt (2026-09-04)

Status: **metadata/input readiness passed; effect training remains blocked.**

This directory records a train-only, outcome-free validation of the approved
historical development protocol.  It is not a model fit, scaling result,
accuracy result, or authorization to open a frozen evaluator.

Bindings and scope:

- protocol SHA-256: `1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902`
- unchanged frozen-v2 SHA-256: `3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9`
- remote aggregate summary SHA-256: `c40f9b696530c2303c5129fa5571a2ffc484986472d1962871170d30a509043b`
- 30 plans = 2 candidate distributed shapes × 3 seeds × 5 arms
- 30 independent source-descriptor replays and 6 cross-arm relation checks passed
- GPU jobs / API calls / model fits / model weights loaded: all 0
- dev, test, prospective, label-vault, prediction and utility values opened: 0

Verified real-input accounting:

| arm | pair visits (seed 6/7/8) | valid-token shortfall (seed 6/7/8) | optimizer updates |
| --- | --- | --- | --- |
| L1 | 4,689 / 4,689 / 4,689 | not a matched-budget arm | 37 |
| Lbudget | 15,276 / 15,275 / 15,273 | 2,720 / 1,937 / 2,066 | 121 |
| Gbudget | 13,519 / 13,557 / 13,517 | 5,367 / 711 / 593 | 107 |
| G→L | 14,081 / 14,081 / 14,081 | 0 / 0 / 0 | 111 |
| Ghash→L | 14,081 / 14,081 / 14,081 | 0 / 0 / 0 | 111 |

The common cap is 104,863,947 valid tokens.  A baseline stops before the first
whole pair that would overshoot; it never splits code or pads with repeated real
pairs.  Update counts are intentionally reported rather than falsely called
matched.  Every complete source cycle ends at an optimizer boundary, making L1
the exact first-pass optimizer/LR prefix of Lbudget.  G→L and Ghash→L have the
same input-plan hash for every shape and seed; only the global targets differ.

The guarded work itself returned success and atomically wrote `summary.json`.
The surrounding PowerShell→SSH bash wrapper then exited nonzero because a CRLF
character was appended to its final numeric `exit` argument.  This transport
failure is retained in `execution_context.json`; it occurred after the workload
reported `REMOTE_RC=0`.  A separate direct Python invocation, with no source-data
access and no bash wrapper, verified the aggregate receipt and returned rc=0.

