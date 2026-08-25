# 0823 prospective batch structural postflight

This GitHub-accessible copy binds the final outcome-blind 0823 batch postflight
at snapshot
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1`.
The six observed archives were settled as four accepted transactions and two
whole-archive structural rejections. The quiescence observation was exactly
`archives=218, baseline=128, ready=0, rejected=12, transactions=78`.

Relative to the preceding `f109ac...` snapshot, the accepted archives add 11
eligible physical runs, 204 endpoints, 46 canonical sibling pairs, and one task.
The final provisional first-960 prefix contains 339 runs, 10,196 endpoints,
2,635 pairs, and 30 tasks. Its 334 finite-decision runs cover all 30 tasks; exact
code unique fraction is `0.9970576696743821`, with zero cross-run and zero cross-task
exact-code duplicate groups.

The four per-archive structural deltas are preserved separately:

- Plant Pathology: 4 runs / 50 endpoints / 4 pairs / 1 newly represented task;
- TensorFlow Speech: 4 / 80 / 30 / 0;
- RANZCR: 1 / 13 / 1 / 0;
- Alaska2: 2 / 61 / 11 / 0.

AI4Code and LMSYS were rejected before outcome access under
`JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE`. AI4Code has four
checkpoint journals with identity cardinalities 3×one and 1×zero; LMSYS has
4×zero. No filename inference or partial-run salvage was used.

The independent verifier does not import the production accumulator. Its A/B
runs were byte-identical and cross-checked 12 accumulator fields. The formal
root is
`/research/d7/spc/yzyang4/prospective-0823-batch-postflight/6299865-7cdaefcf-v1`;
the formal `SHA256SUMS` file has SHA-256
`448999c0e6c21e655f44fb8429ef61e0ea1440617ac842d719fb5140dfbed001`.
The checked-in JSON files are byte-identical to that root.

This is a positive corpus-quality and temporal-growth result, not a predictor
effect. The confirmatory gate remains closed: 621 runs are still needed for the
fixed first-960 cohort, accrual closure is absent, and the dominant pair-task
share is 0.31233396584440226 > 0.25. Outcome/label/prediction aggregates were not
read; GPU/API/model-fit counts are all zero.

Failed attempts remain part of the audit trail: the first AI4Code audit wrapper
included its own scan output; the first four-archive batch wrapper omitted the
repository working directory; and the first pre-push bundle verifier requested
a nonexistent bundle `HEAD` ref. Each failed before changing the scientific
claim, and the corrected runs used fresh output roots.
