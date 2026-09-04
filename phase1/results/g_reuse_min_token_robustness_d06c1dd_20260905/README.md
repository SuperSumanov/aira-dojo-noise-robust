# G-reuse minimum-token basis cap/task robustness

Date: 2026-09-05 Hong Kong. Result-before source commit:
`d06c1dd159c1f84a6ca11da612ee23ce51ce641a`.

## Frozen test

Rebuild the deterministic minimum-token forest separately with 4K, 8K, 16K,
and uncapped raw endpoint lengths. All four scenarios had to retain per-task and
total rank gain, reduce aggregate G tokens by at least 60%, retain at least 60%
after dropping any one task, keep every task below 20% of saved tokens, and have
at least 20/28 tasks reduce their own G tokens by 50% under every cap.

## Exact result

| cap | basis/full gain | token reduction | minimum leave-one-task reduction | maximum task saved-token share | tasks at least 50% |
|---|---:|---:|---:|---:|---:|
| 4K | 790/790 | 0.7147615808349292 | 0.693619695137129 | 0.17799686722712507 | 19/28 |
| 8K | 790/790 | 0.7043122727789066 | 0.6813034232846982 | 0.16760872000505017 | 19/28 |
| 16K | 790/790 | 0.7054416478015496 | 0.6808470077027935 | 0.16608797279776025 | 19/28 |
| raw | 790/790 | 0.7056101398382122 | 0.6810519823461714 | 0.165953330532593 | 19/28 |

Exactly 19 tasks satisfy the 50% condition under every cap. The frozen breadth
threshold was 20, so the overall status is
`G_REUSE_MIN_TOKEN_BASIS_COST_NOT_ROBUST`. The threshold was not changed.

The defensible partial positive result is narrower: aggregate token reduction is
stable across all four cap choices, remains above 68% after excluding any task,
and no task supplies 18% of the total saved tokens. This does not support saying
that savings are large in nearly every task.

## Verification

Producer A/B and an independently implemented verifier A/B all returned zero with
empty stderr. Their durations were 50.23, 43.62, 42.78, and 42.14 seconds. Both
A/B pairs were byte-identical and producer/verifier metrics matched exactly.
Producer receipt SHA-256 is
`0ec3423748fba065d7233a4f14b8a07f31502049eaa8810973c86fc00acf3061`.
The downloaded result archive SHA-256 is
`37a4d04c01b9bef435d006be93abcc51456c0c36adb76691d956c2388084cf19`.
All ten result files passed the downloaded manifest; credential and identity-key
scans had zero hits. GPU jobs, API calls, and model fits were zero.

The first attempt to archive all of `phase1` failed before the formal run because
an unrelated historical 40 MB LFS object is missing from the server. Its partial
archive was not used. The formal run used an exact-commit whitelist of eleven
Python dependency files; the whitelist count was exact and its local and remote
archive SHA-256 both equalled
`c03d0a907d0ba2b2604e7754fd9808e3d4b0e8aca3d4ed496b2f34399f1af708`.

## Claim boundary

Connectivity/rank preservation is a graph invariant, not an empirical model result.
Cycle edges may improve robustness or optimization, so full G-reuse remains the
effect candidate/control and this basis is only a cost challenger. Historical
source/config/experiment closure, G0 measured cost, and explicit GPU approval are
still required. No selected edge, task, run, or card identity was emitted and no
training pool was written.
