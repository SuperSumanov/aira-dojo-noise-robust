# Independent label-scarce full-execution yield confirmation

Status: `HISTORICAL_INDEPENDENT_LABEL_SCARCE_FULL_EXECUTION_YIELD_NOT_CONFIRMED`.

This package contains the aggregate-only output of the result-blind confirmation on
the strictly v11-disjoint senior-0819 train residual. It emits no endpoint, parent,
task, or physical-run identities and uses no pair orientation, gap, grade, outcome,
code, prediction, runtime, senior test row, or prospective value.

The pre-registered primary was task/run-balanced closure greedy versus the strong
shared-endpoint `uniform_edge` baseline over nested endpoint-budget fractions 1/32
through 6/32. The minimum balanced trajectory integral was 343 closed-edge checkpoints
versus a uniform-edge median trajectory integral of 341, only +0.586510264%, far below
the required +20%. Balanced medians were equal to the baseline at the first two
checkpoints and higher at the remaining four, so the mandatory 5-of-6 strict-win gate
also failed. At 6/32, minimum balanced yield was 99 versus baseline median 99, below
the required 11/10. The overall classification is therefore `NOT_CONFIRMED` and no
threshold, budget, population, or primary method was changed after readout.

All pre-registered terminal diversity controls passed. Descriptively, balanced median
yield at 6/32 was 103 versus 99 while task breadth was 36 versus 27 and physical-run
breadth was 94 versus 70; parent breadth was 94 versus 96. Across all six checkpoints,
the worst balanced tie trajectory never had lower yield than the uniform-edge median.
This is a post-readout breadth-at-near-equal-yield hypothesis, not a promoted v1 claim;
it requires a new, still-unseen graph and a separately frozen Pareto protocol.

## Reproducibility

- source commit: `c7148fbc40ace86441248f7551c3c9b6637b547e`
- frozen protocol SHA-256: `69db0331c92f5912dfb5fcd6ebc3dfeb0838eff090f80390e2137c91bd489581`
- aggregate result SHA-256: `aea7a45b1ad3c7213cf90a508e4e0bba42ba72bfdd4ca9fca539e309d953622d`
- independent verification SHA-256: `13b70a87b4d6c4a49091a1684dc2ab0dec5fc8c064d7c994b7f2b2236c431d63`
- producer A/B and verifier A/B were each byte-identical
- independent verifier imported no producer code and matched every aggregate field
- focused/full tests: `29 passed` / `1580 passed, 47 warnings`
- forbidden opens/network/credential filename/credential blob hits: `0/0/0/0`
- GPU/API/model-fit/base-LLM-update: `0/0/0/0`
- remote formal manifest: `a8a45c14b621b3ff959b97cac89f6b73910e4dea673a02203c12632eb4f784fe`

Files:

- `aggregate_result.json`: every pre-registered aggregate trajectory, summary, and gate.
- `independent_verification.json`: exact non-importing reconstruction receipt.
- `preflight_13.txt`: formal pre-flight contract.
- `focused_tests.txt` and `full_tests.txt`: test receipts.
- `scope_receipt.txt`: explicit non-use and resource scope.
- `remote_SHA256SUMS.txt` and `remote_MANIFEST_SHA256.txt`: remote formal-root receipt.
- `COMPLETE`: empty marker copied from the authoritative formal root.
