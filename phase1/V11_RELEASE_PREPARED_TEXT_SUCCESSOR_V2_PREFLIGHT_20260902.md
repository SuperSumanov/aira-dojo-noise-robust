# v11 missing prepared-text successor v2 — 13-item preflight (2026-09-02)

> This is a bounded release-engineering acquisition, not a predictor experiment. It
> uses the remote Kaggle credential without reading or exporting it, downloads five
> fixed CSV files only, and never accesses prospective evaluation state.

1. **Single objective.** Replace the two `UNSCANNED_NO_PREPARED_TEXT` task states with
   a verified, remote-only prepared-text successor so the unchanged v11 literal scan
   can be rerun on all 25 tasks.
2. **Inputs frozen before download.** The exact two competitions, five filenames, and
   expected CSV headers are fixed in `release_prepared_text_successor_v2.json` after
   both metadata-only file-list probes returned success and before any data download.
3. **No result-dependent selection.** All small tabular text endpoints visible or
   required by the competitions are included: train/test/sample for APTOS and
   train-labels/sample for histopathology. No file may be added or removed after its
   contents are observed.
4. **Bounds.** Each compressed and extracted object is capped at 64 MiB, total
   extracted bytes at 128 MiB, and each network request at 600 seconds. Exactly one
   safe archive member or one direct file is accepted per request.
5. **Isolation.** Downloads enter a new mode-0700 formal staging root. The active
   `mle-bench-data/<task>/prepared` paths must be absent and are not changed during
   acquisition or verification.
6. **Archive safety.** Absolute paths, path separators, `..`, symlinks, extra archive
   members, unexpected filenames, and unexpected output files fail closed.
7. **Content validation.** A standalone verifier checks the exact five-file set,
   headers, positive row counts, byte bounds, SHA-256, absence of symlinks, and
   high-confidence credential-shaped bytes. It emits hashes/counts only, never CSV
   rows.
8. **Independent repetition.** The verifier is run twice into separate outputs and
   must be byte-identical. Promotion, if later performed, requires a third verification
   against the destination and may not overwrite an existing path.
9. **Trace/security.** Network and file traces remain private. Public outputs are
   scanned for credentials and absolute paths. first-960, Target-300, Target-522,
   label/outcome vaults, and prediction escrow are forbidden paths.
10. **Budget/ETA.** Five bounded HTTP requests, at most 128 MiB extracted, CPU only;
    GPU-hours=0, paid-model API=0, model fits=0, base-model updates=0. Expected wall
    time is 5--20 minutes; hard per-file timeout is 10 minutes.
11. **Success gate.** Exact-commit checkout, focused/full tests, five successful
    requests, exact file/header set, producer/verifier equality, security scans all
    zero, and a read-only `COMPLETE` marker are all required.
12. **Failure gate.** Authentication/rules denial, timeout, size overflow, malformed
    CSV, hash drift, unexpected file/member, credential-shaped content, active-root
    collision, or forbidden trace freezes a failure receipt and prevents promotion.
13. **Interpretation.** Verified access and prepared-text coverage are not competition
    data redistribution permission, legal clearance, or proof that every non-tabular
    payload was scanned. Raw CSVs remain remote-only and must never enter Git/LFS.

The next scientific step is a fresh 25-task successor of the already frozen literal
scan and whole-card tier rule. Neither threshold nor tier rule may be changed after
the new task results are observed.
