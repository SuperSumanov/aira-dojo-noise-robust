# Corpus LFS provenance audit

Status: `LEGACY_V4_V5_NOT_BYTE_REPRODUCIBLE_CURRENT_BATCHES`.

This result contains metadata and hashes only. It does not include card content, raw senior
archives, environment files, API credentials, outcomes newly read for analysis, or a merged
corpus. See `summary.json` and the Chinese decision record under
`phase1/实验记录/2026-08-14/CorpusLFS_发布契约审计.md`.

After commit `8b38d9acbe68bb2c66825b8f4dce99496f23aedf` was pushed, a fresh cluster clone ran
`git lfs install --local` and a path-scoped `git lfs pull`. The materialized batch was 1,940
rows and 56,424,624 bytes with the expected SHA-256. The two preceding engineering failures
(shell nounset during environment setup, then missing per-repository LFS initialization) are
preserved in `fresh_pull_receipt.json`; neither failure was treated as missing data.
