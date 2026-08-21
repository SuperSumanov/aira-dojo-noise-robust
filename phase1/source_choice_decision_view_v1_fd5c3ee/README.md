# Immutable Source Choice Decision View v1

This directory is the Git LFS distribution of the formally verified S2 decision-time view controlled by
commit `fd5c3ee0fdfffe399088e2e3a4394598264239a6`. The formal receipts are in
`phase1/results/source_choice_decision_view_v1_20260821_fd5c3ee/`.

The four JSONL files are immutable and uploaded once. Run `git lfs pull` after cloning. Their exact bytes match
the read-only formal directory
`/research/d7/spc/yzyang4/source-choice-decision-view/fd5c3ee-v1/view_a`.

- `train_model.jsonl`: 2,109 groups / 5,739 candidates, with public train winner labels.
- `frozen_model.jsonl`: 778 groups / 2,041 candidates, with zero winner fields.
- `extension_model.jsonl`: 113 groups / 247 candidates, with zero winner fields.
- `cluster_manifest.jsonl`: 3,000 group-level task/run/parent records for clustered evaluation; it is not part of
  the official model input surface.

Candidate model fields are exactly `candidate_id_sha256`, `code`, `code_sha256`, `operator`, `step`, and
`depth`. Post-selection `provenance` and `source_journal_sha256` are absent from every model object. The frozen
and extension label vault is not included anywhere in this release.

Before LFS staging, all four local payloads matched their formal SHA-256 values, row counts were
2,109/778/113/3,000, and the credential filename/content scans both returned 0. Do not replace or append to
these files; publish any future revision under a new immutable directory and protocol.
