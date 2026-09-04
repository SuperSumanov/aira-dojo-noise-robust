# G-reuse effect: outcome-blind CI-power sensitivity

Date: 2026-09-05 Hong Kong. Frozen protocol commit: `26a9bfa`; fixture-only repair commit:
`b27115a`. This reads only the 28 anonymous `local_pairs` counts in the already public
historical structural receipt. It reads no labels, predictions, accuracy, utility, identities,
or protected cohort fields.

The first formal root stopped before calculation because the now-bound protocol was copied by
a test that still expected the placeholder SHA: 3 tests passed and 1 failed. That root is
preserved at `formal-26a9bfa-v1`. The replacement test explicitly writes the placeholder into
its temporary copy; no scientific input, formula, grid, scenario, or threshold changed.

The successful root is `formal-b27115a-v2`. Four tests passed. Producer A/B and verifier A/B
are byte-identical. The independent verifier checked all 240 grid rows; maximum power difference
was `3.3306690738754696e-16`. Protocol SHA-256 is
`604dc77095a0f467185d3b4304e52b835f12ba063a2303b133041046cf007c04`; source archive SHA-256 is
`09c50ffc662eada8553216858e6774de69f67f8ed07a043cf32f770aa398f87e`.

The historical structure has 4,689 local pairs across 28 tasks, with harmonic mean 67.9884 pairs
per task. For a true +0.02 paired-accuracy effect, the two-sided 95% task-CI lower-bound gate has:

| Frozen scenario | CI-gate power | 80%-power MDE | Tasks for 80% at +0.02 |
|---|---:|---:|---:|
| optimistic: q=.10, task SD=0, seed rho=0 | 0.9960097411 | 0.0121524294 | 12 |
| reference: q=.20, task SD=.01, seed rho=.5 | 0.6140229369 | 0.0248984446 | 43 |
| stress: q=.40, task SD=.02, seed rho=1 | 0.2509513140 | 0.0434406760 | 126 |

The reference scenario therefore triggers the pre-frozen design warning. These are assumption
sensitivities, not estimated nuisance parameters and not a power guarantee. They model only the
CI gate. The actual core protocol additionally requires the observed point estimate to be at
least +0.02, all three seed signs to be positive, and several comparator/LOTO gates. Hence overall
core success probability cannot exceed the reported CI-gate power. Under a symmetric estimator,
a true effect exactly equal to the +0.02 observed-effect threshold passes that point threshold with
probability at most one half.

Decision: do not weaken the +0.02 gate and do not enlarge an evaluation set after opening outcomes.
Before GPU approval, the authoritative package must supply anonymous per-task evaluation support;
the same outcome-blind calculation must be repeated on that exact frozen structure. If support is
near the current 51-task corpus breadth it may clear the reference sensitivity, but 51 corpus tasks
does not imply 51 effect-evaluation tasks. No GPU, API, model fit, or protected read occurred.
