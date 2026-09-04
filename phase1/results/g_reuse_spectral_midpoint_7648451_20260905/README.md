# Cost-aware spectral midpoint selector

Date: 2026-09-05 Hong Kong. Result-before commit:
`76484510fbee05c8bbd16df476209e30e9671c82`.

## Frozen comparison

For each task, the additional G-token ceiling is half (floored) of the gap between
the 790-edge minimum-token basis and all 2,745 G edges. Starting from `L + basis`,
the spectral arm greedily adds the fitting edge with maximum
`log1p(current effective resistance) / edge tokens`. Scores are rounded to fifteen
decimal places before deterministic endpoint-ID tie-breaking. Cheapest-first and
SHA-256 order use exactly the same per-task ceilings.

The two absolute fidelity gates were aggregate D-opt capture at least 75% and median
task D-capture at least 70%. Comparative gates required spectral to beat both
baselines on aggregate D- and A-opt capture, be non-inferior on at least 20 cycle
tasks, stay within every task budget, and use at least 95% of the aggregate budget.

## Exact result

| selector | additional tokens / ceiling | utilization | aggregate D capture | aggregate A capture |
|---|---:|---:|---:|---:|
| spectral | 6,836,387 / 6,913,983 | 0.9887769466601234 | 0.7268336658528469 | 0.8744405497929161 |
| cheapest | 6,822,756 / 6,913,983 | 0.9868054347255409 | 0.599808606698623 | 0.5923756743213272 |
| SHA-order | 6,857,649 / 6,913,983 | 0.9918521639408139 | 0.6222128940985481 | 0.7365262129330473 |

Spectral is D-non-inferior to both baselines in 24/27 tasks with cycle headroom,
and its median task D-capture is `0.68697301897845`.

The spectral arm passes all budget and comparative gates, including the A-opt
metric it did not directly optimize. It fails both frozen absolute gates:
`0.7268336658528469 < 0.75` and `0.68697301897845 < 0.70`. Therefore the overall
status is `G_REUSE_SPECTRAL_MIDPOINT_NOT_SUPPORTED`; thresholds were not changed.

The defensible partial positive result is relative: under the fixed midpoint token
ceilings, the spectral selector retains more D- and A-opt graph information than
both simple controls. It did not achieve the predeclared absolute fidelity target.

## Verification

The producer uses shifted-Laplacian inverses; the independent verifier uses grounded
Laplacian inverses. Producer A/B is byte-identical. Verifier A/B and
producer/verifier metrics agree within the frozen `rel=1e-8, abs=1e-7` tolerance;
their maximum absolute differences were `1.8189894035458565e-12` and
`1.127773430198431e-10`, respectively, with zero non-float differences. All four
runs returned zero with empty stderr; durations were 51.04, 43.21, 43.81, and 45.00
seconds.

Producer receipt SHA-256 is
`fd474f1c23dca9d3ee9547710e656aa59cbfc737b8bb6bd7841e0069fb0664f2`.
Downloaded result archive SHA-256 is
`d14c51f261796e070e5d755f2acb0005d9c3882512a27ab322836ade667b6a84`.
The exact-commit twelve-file source archive had identical local/remote SHA-256
`64116f516bb225e065dab8db398afcd79742acfdf8494e6a1a2005fe7a584e91`.
All ten output files passed the downloaded manifest; credential and identity-key
scans had zero hits. GPU jobs, API calls, and model fits were zero.

## Claim boundary

This is graph-information efficiency, not neural critic accuracy, execution savings,
or a novel spectral method. The SHA arm is a deterministic neutral order, not a
random-baseline distribution. A later 25/50/75 curve may test whether relative
dominance persists, but it cannot overwrite the failed midpoint thresholds. Model
evaluation still requires coherent producer provenance, G0 cost, explicit GPU
approval, same-budget multi-seed comparison, and untouched confirmation data.
