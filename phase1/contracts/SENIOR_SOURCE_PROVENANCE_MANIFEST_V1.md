# Senior source provenance manifest v1

This is the producer-to-consumer contract required to replace date/config proxies with exact physical-experiment identity.
It does not contain code, stdout, grades, model predictions, or pair orientation.

## Canonical JSONL row

Rows must be sorted bytewise by `run_id`; every row has exactly these fields:

```json
{"archive_path":"0808/example-task-8seeds.tar.gz","archive_sha256":"<64 lowercase hex>","batch_id":"<exact top-level tar directory>","producer_commit":"<full 40-hex git commit>","run_id":"<frozen run id including __YYYY-MM-DD>","source_date":"2026-08-08","task":"example-task"}
```

- `run_id` must occur exactly once and the manifest must cover every row in the frozen expected-run manifest—no subset
  salvage and no extra runs.
- `task` and `source_date` must match the frozen run row and the date suffix in `run_id`.
- `archive_path` is a canonical relative POSIX path below the supplied source root; its first directory is the matching
  `MMDD` day (an explanatory suffix after `MMDD-` is allowed).
- `archive_sha256` binds immutable source bytes; `producer_commit` binds the code/config provenance known by the producer.
- `batch_id` is the exact top-level tar directory containing the physical run, not a date/config-derived proxy.

## Independent acceptance command

```bash
python phase1/validate_senior_source_provenance_manifest.py \
  --expected-runs <frozen-run-manifest.jsonl> \
  --expect-runs-sha256 <sha256> \
  --provenance-manifest <producer-provenance.jsonl> \
  --expect-provenance-sha256 <sha256> \
  --source-root <archive-root> \
  --output <new-receipt.json>
```

The consumer validator is independent of all pair/corpus producers. It verifies exact schema and full run coverage, checks
every referenced archive's SHA-256 and regular-file/no-symlink status, then scans tar headers to require exactly one matching
`<batch_id>/<source-run>/checkpoint/journal.jsonl`. It rejects link/device/FIFO members and never calls `extract` or
`extractfile`, so member payloads are neither exposed nor parsed (the compressed archive bytes are still hashed and streamed).

`PROVENANCE_VERIFIED` only means the identity join is complete and reproducible. It does not validate model effects and does
not by itself authorize a GPU experiment. The corrected 0811/0812 leaf archives and canonical handling of the rejected 0730
and 0809 tabular archives must still be represented by valid, hash-bound rows for every affected run.
