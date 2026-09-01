# 517-run WL escrow snapshot-chain structural receipt

This directory records the outcome-blind structural postflight for the frozen WL
escrow at snapshot `e9e12c639fde...e8a6d`. The remote formal root is immutable
(`0500`) and contains 52 files with `COMPLETE`, no `FAILURE`, and no `FAILED_RC`.
The producer, non-importing independent verifier, and snapshot-chain verifier all
returned `0`; the full remote `SHA256SUMS` check passed.

The append-only extension is exact: 494 prior eligible runs plus 23 additions and
zero removals produce 517 current runs. The previous 13,098 endpoint rows and
3,230 pair rows remain exact; the current escrow contains 13,581 endpoints and
3,325 pairs, adding 483 endpoints and 95 pairs. Frozen-order and prior-set/
sequence invariants all pass.

This is a positive **benchmark coverage and audit-protocol** result. It is not a
predictor-accuracy, scaling, effect-size, or search-utility result. The first-960
cohort is not closed, so the support gate remains provisional. The receipt-support
chain also remains at the previous snapshot because its required transition was
not restarted: that path performs model fits and needs separate authorization.

Only structural receipts, return codes, runtimes, and hashes are copied here.
Prediction artifacts, the artifact summary, traces, commands, and the full
independent-verification payload are intentionally omitted. No prospective
outcome, prediction value, candidate identity, or candidate profile was read.
GPU/API/model-fit/base-LLM-update usage was `0/0/0/0`.

At the recording time (`2026-09-01T15:18:34Z`), the senior source still contained
283 archives and LATEST remained the same 517-run snapshot; no new stable corpus
snapshot had arrived.

## Exact-commit post-push verification

Public commit `cbb22c5bce60b6eb592a10da4bf9672212d7866a` was checked in a fresh
no-smudge worktree with the project's complete remote environment. The first
verification root is retained as a failed harness attempt: its focused tests
passed 6/6, but pytest was launched from the remote home directory, so 16 tests
that use repository-relative paths failed with `FileNotFoundError` while 1,919
passed. No scientific or release code changed.

The fresh v2 root changed only the process working directory to the exact
worktree. It passed the same focused tests (`6 passed`) and the complete suite
(`1,935 passed`, 48 warnings) in 122.59 pytest seconds. Its 13-item preflight,
credential scans, clean-worktree check, resource scope, and full manifest all
passed; the root is immutable with `COMPLETE`. The v1/v2 manifest SHA-256 values
are `70ed232f...fae0a` and `d27e9da9...e0421`. The local Windows full-suite
attempt is not counted because that environment lacks the repository's existing
SciPy/scikit-learn dependencies.
