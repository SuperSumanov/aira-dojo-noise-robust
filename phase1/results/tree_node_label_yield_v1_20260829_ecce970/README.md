# Tree Node → Sibling Label Yield v1 aggregate result

Status: `HISTORICAL_GRAPH_AWARE_FULL_EXECUTION_LABEL_YIELD_NOT_ESTABLISHED`.

This package contains only aggregate topology-replay output. It emits no endpoint,
parent, task, or physical-run identities and uses no pair orientation, gap, grade,
code, prediction, runtime, or prospective value.

The pre-registered primary comparison was task/run-balanced closure greedy versus
the strong shared-endpoint `uniform_edge` baseline. The balanced method passed all
breadth and anti-dominance gates and beat the baseline at five of six budgets, but
failed the mandatory 6/5 yield gate at the 2,048-endpoint headline budget. The
overall classification therefore remains `NOT_ESTABLISHED`; no threshold, budget,
population, or primary method was changed after readout.

## Headline aggregate medians

| endpoint budget | balanced closed edges | uniform-edge closed edges | relative difference | yield gate |
|---:|---:|---:|---:|:---:|
| 512 | 422 | 285 | +48.070175% | pass |
| 1,024 | 806 | 628 | +28.343949% | pass |
| 2,048 | 1,479 | 1,420 | +4.154930% | fail |

At 4,096 endpoints the medians were 3,163 versus 3,222, a -1.831161%
difference. This supports only a post-readout diagnostic that topology-aware yield
may be a low-budget phenomenon; it is not a promoted v1 conclusion.

## Reproducibility

- source commit: `ecce9702591b5950a63f1e58f4d56fb46cb6289a`
- frozen protocol SHA-256: `b32f7ba39aff81b5d5637530e0e0e73b2b9a655c56c83cc99d087bc0075cf881`
- aggregate result SHA-256: `dad4197b8172bd8e7a7ff785f35cddc722397574c680bd587d42fbcf7dfb1e2a`
- independent verification SHA-256: `82d2008268aea3607d4c0ab41b53e4f1525ad10a48a08c29ab4e4c5342e453cc`
- producer A/B and verifier A/B were each byte-identical
- independent verifier status: `INDEPENDENT_RECONSTRUCTION_EXACT`
- focused/full tests: `7 passed` / `1558 passed, 47 warnings`
- network/prospective opens/row identities: `0/0/0`
- GPU/API/model-fit/base-LLM-update: `0/0/0/0`

Files:

- `aggregate_result.json`: all pre-registered aggregate trajectories and gates.
- `independent_verification.json`: non-importing exact reconstruction receipt.
- `preflight_13.txt`: formal pre-flight contract.
- `full_tests.txt`: full phase test receipt.
- `COMPLETE`: immutable remote completion receipt copied from the formal root.
