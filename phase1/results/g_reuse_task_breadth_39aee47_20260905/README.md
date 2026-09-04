# Historical G-reuse task-breadth result

Date: 2026-09-05 Hong Kong. Formal source commit:
`39aee477e6adc3d6284926b5f0a2a896c841d1de`.

## Frozen question and gates

The result-before preflight fixed three simultaneous support gates:

1. at least 20 tasks have strictly positive incidence-rank gain;
2. the largest single-task gain share is at most 0.20;
3. dropping any one task retains at least 0.80 of total gain.

No task, threshold, input, or rescue analysis was changed after seeing the result.

## Exact result

- tasks with positive gain: 28 of 28;
- total incidence-rank gain: 924;
- maximum single-task gain: 79;
- maximum single-task share: `0.0854978354978355`;
- minimum leave-one-task retained fraction: `0.914502164502164`;
- all three gates: PASS;
- status: `HISTORICAL_G_REUSE_TASK_BREADTH_STRUCTURALLY_SUPPORTED`.

Producer A/B and independent-verifier A/B all returned zero with zero-byte stderr.
Producer and verifier aggregates match exactly. The producer receipt SHA-256 is
`1f52670c0138a5ef8f222092c801f07a70863ae940ff4af77fd0231e6e16eb10`.
The downloaded archive SHA-256 was
`6d400e787085465e14e86c0348ac64dc83c637cc8120f36a3fdee972247ae13f`,
and every file passed the included `SHA256SUMS` manifest. Credential-shape scan was clean.

The four recorded run durations were 50.23, 42.31, 76.02, and 77.36 seconds.
GPU jobs, paid API calls, and model fits were all zero.

## Claim boundary

This excludes concentration in a few tasks as an explanation for the known aggregate
structural gain. It does not establish accuracy, effective independent sample size,
clean scaling, model improvement, or search utility. Config/source/experiment-closure,
G0 costing, and explicit training-budget gates remain unresolved; this receipt does not
authorize model training.
