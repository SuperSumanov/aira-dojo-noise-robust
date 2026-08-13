# ParentPatchCritic sparse V3a result

Run date: 2026-08-14. Scientific source commit:
`38c26cac2c7df23809ca5477ceefeb472f06dc90`. The run used one CPU process, no GPU and no API.

## Audit trail

- The first V3 launch at commit `500f8134e90f2d98bdfac61df62206f354cba528` stopped after train
  structural audit with `INVALID`: raw train had 333 runs but parent-present common support had 280.
  It produced no representation, fit, prediction or accuracy and recorded `frozen_read=false`. Its unedited
  summary and launcher log are retained as `prior_invalid_*`.
- Before any prediction outcome existed, V3a amended only the structural run floor from 300 to 250. Model,
  features, folds, seed and every effect/success threshold stayed fixed. The amended protocol was committed and
  pushed before this run.
- V3a ran on 3,948 parent-present pairs from 280 physical runs and 23 tasks. Parent coverage was
  0.9261083743842364 and dominant-task share was 0.2188449848024316.
- Runtime was 348.4082453129813 seconds. The discovery gate closed and the program recorded
  `status=DISCOVERY_NO_UNLOCK`, `frozen_read=false`; there is no frozen prediction file.

## Discovery result

| Metric | whole child code | parent→child line patch | patch − whole |
|---|---:|---:|---:|
| OOF pair accuracy | 0.5177304964539007 | 0.5030395136778115 | -0.014690982776089158 |
| parent-macro top-1 | 0.4519505233111323 | 0.4462416745956232 | -0.005708848715509039 |

The pair-difference run-macro estimate was -0.05817862421245462 with 95% CI
[-0.09934570209589642, -0.017028982231711703]. Its task-macro estimate was -0.0239384920330049
with 95% CI [-0.051675473956106, 0.0015258012456187287]. Among 20 tasks with at least 20 rows,
5 were nonnegative (share 0.25). The absolute patch accuracy, relative gains, run/task uncertainty and task
consistency gates all failed. This closes the pre-registered sparse line-diff implementation; it does not establish
that all parent-conditioned or semantic edit representations fail.

## Independent verification and numerical incident

The launcher-time verifier first exited because direct sparse pair margins and separately evaluated endpoint-score
differences can differ by floating-point operation order. The preregistered `1e-5` redundant-algebra tolerance was
too tight: only 7 absolute rows and 2 patch rows exceeded it. A read-only audit found maximum discrepancies
1.6033649444580078e-05 and 1.0967254638671875e-05, with zero orientation mismatches, zero saved-hit mismatches,
and identical direct/endpoint accuracies for both arms. No value exceeded `1e-4`.

After the outcome, only the independent verifier tolerance was changed to `1e-4`; no model or scientific gate was
rerun or changed. Corrected verifier source SHA-256 is
`18cb757fc7932afbeb089a2f91670ce87dfa392935322c440b4288a7ddf065e0`. It independently reconstructed all
metrics and gates from the immutable CSV and passed with `DISCOVERY_NO_UNLOCK`, 3,948 rows and
`frozen_verified=false`.

## Canonical Git/remote artifact hashes

- `summary.json`: `50819a7eea19e6bd4522468ab329ad6f51508512df5b2abd736bc4972acbbd12`
- Git-viewable LF-normalized `oof_predictions.csv`:
  `21e107fbfcd59460c0ef6ef91e81d4f4da745da8402b5b7d65583d77a3b5ba1e`
- Source-byte `oof_predictions.original.csv.gz`:
  `03176a9d8d6e9bf335eb74b5df5b69706e794e30ff84e8d4eb62814ad206ebd1`;
  decompressed SHA-256 (the value recorded by `summary.json`):
  `0432c3449772e3b7d7ef692cca91d4d29c52b68282de7eba420e653cfa41cc9f`
- `launcher.log`: `585ead872358ab0488b2e003a3b452b9813d9297e83daecd79f1b53bd255ae5b`
- `independent_verify.json`: `997e891cd18b02a24b2a214a3b903e424dd72317bb0fc1573b74a5a01bd26e01`

The experiment CSV uses RFC-style CRLF. GitHub's viewable copy is deliberately LF-normalized; the deterministic
gzip stores the exact source bytes and round-trips to the immutable SHA in `summary.json`.
