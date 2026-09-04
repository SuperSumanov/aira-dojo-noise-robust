# G-reuse record-consistency sensitivity

Date: 2026-09-05 Hong Kong. Frozen-gate commit:
`fe9aec186a6a1e67d5764e59126549b39155a3e5`; corrected as-run commit:
`e4d89b0f3a6a42d1b019676c1a970b202856c022`.

## Frozen analysis

From all 3058 historical G-reuse edges, exclude the union of edges whose two observed
card configs differ or for which either endpoint run lacks a unique source projection.
This retains the previously reported 2745 `equal observed config + unique projected
source` edges. Three gates were fixed before result readout:

1. retain at least 0.80 of the full 924 incidence-rank gain;
2. at least 20 tasks retain positive rank gain;
3. maximum single-task share of filtered gain is at most 0.20.

## Exact result

- filtered/full edges: 2745/3058;
- filtered/full incidence-rank gain: 790/924;
- gain retention: `0.854978354978355`;
- tasks with positive gain: 28/28;
- maximum single-task gain: 72;
- maximum single-task share: `0.09113924050632911`;
- all three gates: PASS;
- status: `RECORD_CONSISTENT_G_REUSE_SENSITIVITY_SUPPORTED`.

Producer A/B and independent-verifier A/B all returned zero with zero-byte stderr;
their aggregates match exactly. Durations were 48.60, 41.53, 41.37, and 40.98 seconds.
The producer receipt SHA-256 is
`efdc900685a892cf5b623f365d76faa93f8762e088efa5799abf04568d810ad2`.
The downloaded archive SHA-256 is
`9c947bb9f7cdf73c9a6b87c4e11bdfee98208aee24a8224119e16224f7602065`;
all internal manifest hashes and the credential-shape scan passed. GPU jobs, API calls,
and model fits were zero.

## Preserved failure

The first formal root at source commit `fe9aec1` failed before metric production because
the caller indexed a `reuse_pairs` field that the task summarizer does not return. It
produced only `FAILED_CLOSED/KeyError`, with empty stderr; neither producer B nor a verifier
ran. The correction explicitly binds edge counts and adds an integration test. Inputs,
exclusions, thresholds, and gates did not change, and the retry used a new source/result root.

## Claim boundary

This supports robustness of the historical structural gain to excluding the 313 edges
with known record-level issues. Observed-config equality is not producer attestation, and
a unique old projection is not authoritative source repair. The Cards and G inputs still
do not form one complete producer package, and experiment closure remains unverified.
The 2745 edges are not a clean training pool and this receipt does not authorize training,
accuracy claims, scaling claims, or search-utility claims.
