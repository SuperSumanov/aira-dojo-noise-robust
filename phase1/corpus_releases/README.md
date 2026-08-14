# Immutable corpus releases

Git LFS stores only immutable per-batch JSONL payloads. `batch_registry.json` is
append-only, and every release descriptor pins three independent contracts:

1. the ordered batch prefix via `batch_count` plus `batch_lock_sha256`;
2. the historical byte-serialization protocol via `rebuild_protocol`;
3. the output row count, byte count, and SHA-256.

From a clone whose `origin` is this fork:

```bash
git lfs install --local
git lfs pull --include='phase1/cards_*.jsonl'
bash phase1/rebuild_corpus.sh v11 /tmp/cards_current_v11.jsonl
```

If the fork is named `fork` and `origin` points to Facebook upstream, use
`git lfs pull fork --include='phase1/cards_*.jsonl'`. The rebuild fails closed on
an unsmudged pointer, a changed/missing batch, a changed batch lock, segmentation
violations, or any output row/byte/SHA mismatch. It also writes a receipt beside
the rebuilt output.

Verified releases are v6 through v11. On 2026-08-14, each was independently
rebuilt with its historical code and compared byte-for-byte with its frozen
original. v4 and v5 predate the first LFS batch publication; their named payloads
were changed in place before LFS and the original merged files were not retained.
Their explicit non-release status is recorded in `legacy_v4_v5_status.json`; they
must not be presented as reproducible releases.

For a new release, append one immutable batch record, never edit an existing one,
then add a new version descriptor after an independent fresh-clone rebuild matches
the frozen target exactly.
