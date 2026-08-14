# Selective execution v11 retrospective discovery

Formal verdict: **`SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`**.  This is a registered secondary analysis of
already-observed v11 train-run OOF predictions, not an independent confirmation.  It did not open frozen/test/
first-960 outcomes.

The fixed `tri_unanimous_q20` policy selected 293 of 1,520 exact-two parents across 129 runs and 22 tasks.  It
would reduce candidate executions from 3,040 to 2,747, a count-based saving of `0.09638157894736842`; this is not
an observed GPU-time saving.  Accuracy was `0.5494880546075085` pair-micro,
`0.5572152868664496` run-macro (95% CI `[0.48208440999138674,0.6329395841023748]`), and
`0.5575913930507589` task-macro (95% CI `[0.4780537058575693,0.6436459274377935]`).  The task-macro delta over
the same-cost `char_margin_matched` control was `+0.03502779307071244`, but its task-bootstrap CI
`[-0.05286426757718625,0.13190540852024105]` crossed zero.  Margin enrichment within the unanimous pool was
not supported (`-0.03710220722646631`, CI `[-0.1020062027524714,0.023704664553946854]`).

Producer source commit: `7a1562a4506f17d713467956c797fb0d3226a8c5`.  The independent implementation reports
`INDEPENDENT_SELECTIVE_EXECUTION_VERIFY_PASS`; summary SHA-256 is
`f12e5bbf7b1b97aca4ea05a01946882977c5bd5c1a98c17ae7736bccab18748b` and selected-parent SHA-256 is
`676aaef235e03fe79aa256786616b684c3969ee13f5eec2f2be83ab93eb32787`.

The first launcher completed producer and verifier but failed during final hash verification because `run.log` was
still being appended while it was represented in `SHA256SUMS`.  The bad manifest is preserved as
`SHA256SUMS.failed_self_reference`.  Commit `98065c85c1900c6b1ba1e0632204ab8ad63d44db` repaired only the
postflight sequence; `postflight_repair_receipt.json` records that neither scientific program was rerun.  The repaired
payload manifest SHA-256 is `c58154d8772ac4e2c2bb3edc6481ac07a6eb801fc9e3261b254ec94a0254c379`.

The q=0.05 curve point (65 parents/18 tasks) is descriptive and below the frozen primary support/coverage point.  It
must not be used to change q, delete tasks, or nominate a prospective policy after this no-unlock verdict.
