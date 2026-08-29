# Historical independent sibling graph qualification

Status: `HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE`.

This package is the authoritative r2 result for the pre-registered population
qualification gate. It contains aggregate counts and irreversible fingerprints only;
no endpoint, parent, task, or physical-run identities are emitted. It does not contain
an acquisition curve, pair orientation, gap, grade, code, prediction, runtime, senior
test row, or prospective first-960/Target-300 value.

The senior-0819 train-only direct-sibling core contains 952 pairs from 327 physical
runs and 37 tasks. The frozen strict exclusion removes every row whose endpoint,
declared parent, or physical run overlaps v11 train:b0. The resulting independent
graph has 539 unique pairs, 1,036 endpoints, 505 parents, 190 physical runs, and 36
tasks. Exact pair/endpoint/parent/run overlap with v11 is 0/0/0/0; duplicate and
reverse-orientation conflicts are both zero. All eight integrity gates and all eight
support gates pass.

The graph is sparse: it has 505 connected components and maximum endpoint degree 4.
Therefore this qualification is a positive population asset, not evidence that a
topology-aware acquisition rule has a global advantage. Any label-yield confirmation
must be frozen separately before this graph's curves are read and should state its
label-scarce estimand explicitly.

## Reproducibility

- authoritative source commit: `7ad83d2afa16c30df1464bdbe5fbb17ac16ac7c4`
- frozen protocol SHA-256: `b033ddbe99c94a0e9e924233181879121e8a3f2021d86278210f58d1fa720c4c`
- producer result SHA-256: `ea66df81b640c8623936c40bd2742245361c684f6d270ef53b59f4432e65fa18`
- independent verifier SHA-256: `6f7c3a3ca782e4d18d9d67ee6954f0a6bcbbafedac0d1a134a1b1fdfa6e0c8a1`
- producer A/B and verifier A/B were each byte-identical
- independent verifier imported no producer code and matched every aggregate field
- focused/full tests: `15 passed` / `1573 passed, 47 warnings`
- forbidden opens/network/credential filename/credential blob hits: `0/0/0/0`
- GPU/API/model-fit/base-LLM-update: `0/0/0/0`

The earlier r1 completed the scientific computation but exited at the final scanner
with `FAILED_RC=90`: the old credential regex matched `sk-` inside ordinary
`task-...` text. r2 changed only that operational boundary check, added positive and
negative scanner self-tests, and reproduced the r1 producer/verifier hashes exactly.
r1 is retained rather than silently discarded.

Files:

- `formal_summary.json`: authoritative aggregate qualification output.
- `verification.json`: non-importing exact reconstruction receipt.
- `preflight_13.txt`: frozen pre-flight contract.
- `focused_tests.txt` and `full_tests.txt`: test receipts.
- `scope_receipt.txt`: explicit non-use and resource scope.
- `remote_SHA256SUMS.txt` and `remote_MANIFEST_SHA256.txt`: remote formal-root receipt.
- `r1_FAILED_RC.txt`: retained operational failure code.
- `COMPLETE`: empty marker copied from the authoritative remote r2 root.
