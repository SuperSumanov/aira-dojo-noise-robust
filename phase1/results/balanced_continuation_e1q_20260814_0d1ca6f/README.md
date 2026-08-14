# Balanced continuation E1-Q fresh-anchor pilot

Source commit: `0d1ca6fd948d24f23d4abecc3298d8ff6ef53974`. Final collection status:
`VERIFIED_COMPLETE_REAL_E1_COLLECTION`; independent compact-archive status:
`VERIFIED_INDEPENDENT_E1_ARCHIVE_ANALYSIS`. The frozen interpretation remains descriptive-only, with
`primary_gate_claim_allowed=false` and `e2_e3_unlocked=false`.

## Integrity and cost

- 8/8 rollout jobs, 16/16 candidate execution attempts and processes, 8/8 Qwen operator calls;
- zero operator retry, candidate retry or analyze call; `dtest_rows_read=0`;
- stage 1 and stage 2 both passed their score-blind engineering gates; all 16 sealed D_val receipts were opened
  only after the complete-coverage gate;
- eight unique workspaces and tokens; no in-flight rollout at collection time;
- total candidate wall time `4918.986782835971` seconds, or `1.3663852174544364` realized candidate GPU-hours;
- archive manifest: 16/16 downloaded payloads match; suspicious filenames and high-confidence credential files
  are both zero.

The compact collection's five files were independently re-enumerated: 8 rollout rows, 4 sibling rows, 2 task
rows and every summary aggregate. Its summary SHA-256 is
`f98ee3d663fab2d1085ec9cefcf14c36d17e15b966ba45eb90ef538f49f92d11`.

## Descriptive outcomes

Both tasks selected the same sibling in both replicate blocks, so task-level replicate ranking agreement is
2/2. The four policy-indexed sibling labels are:

| task | sibling | balanced `V_1` mean | sample variance | mean gain over warm | practical-success probability |
|---|---|---:|---:|---:|---:|
| spaceship-titanic | `44418a…` | `0.7720870678617158` | `0.0` | `0.0` | `0.0` |
| spaceship-titanic | `d6d06a…` | `0.7842509603072984` | `7.3775208578908168e-06` | `-0.003841229193341844` | `0.0` |
| tabular-playground-series-may-2022 | `94714e…` | `0.9368174942536369` | `6.7506581876294324e-10` | `0.00011822281112028321` | `0.0` |
| tabular-playground-series-may-2022 | `fb413d…` | `0.0` | `0.0` | `0.0` | `0.0` |

There were 2/8 positive-gain rollouts, both very small, and 0/8 gains reached the frozen practical threshold
of `0.01`. Task mean gains were `-0.001920614596670922` for spaceship and
`0.000059111405560141606` for tabular.

The preregistration therefore maps this result to `E1Q_LABEL_FEASIBILITY_OBSERVED`: complete matched repeated
labels exist and are non-degenerate, with consistent within-task sibling ordering in this two-anchor pilot.
This is not evidence that the ordering is reliable across anchors/tasks, that continuation improves solutions,
or that a critic trained on these labels improves search.

## Execution-status reporting repair

The frozen compact schema accidentally omitted the preregistered execution-status/submission-validity detail.
It was not regenerated or edited. A post-hoc status-only repair read the 16 execution receipts that had already
passed the independent worker verifier, rejected credential-shaped bytes before JSON parsing, and exported no
code, terminal output or raw operator response. It reports:

| stage | ok | execution error | timeout | artifact present | D_search/D_val scored |
|---|---:|---:|---:|---:|---:|
| warm | 6 | 2 | 0 | 6/8 | 6/8 |
| continuation | 6 | 1 | 1 | 6/8 | 6/8 |

Thus 25% of continuation executions did not yield a scored artifact, while gains conditional on scored
continuations were small in this pilot. This is a concrete reason to keep validity and conditional gain as
separate future targets, but it does not demonstrate that a hurdle critic works. The reporting repair did not
change collection values, stopping, anchor selection or the E1 verdict; its source receipt hashes and scope are
in `status_audit/status_audit.json`.

## Decision

E1-Q closes the feasibility gate positively and the practical-improvement gate negatively/descriptively. E2
must be redesigned from the observed validity, variance, support and cost, then separately approved; no E2/E3
job is authorized by this result. The stable paper mainline remains the run-clean, choice-set-faithful dataset
and first-960 prospective confirmation.
