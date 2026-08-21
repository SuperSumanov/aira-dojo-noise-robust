# Immutable Source Choice Decision View v2

This is the corrected, formally verified model view controlled by commit
`3ceb99f8030fb196d2abc388e277b11dbd1bc571`. Run `git lfs pull` after cloning. The four JSONL payloads are
immutable and match the read-only formal directory
`/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2/view_a` byte for byte.

- `train_model.jsonl`: 2,109 groups / 5,739 candidates and public train winner labels.
- `frozen_model.jsonl`: 778 groups / 2,041 candidates and no public winner labels.
- `extension_model.jsonl`: 113 groups / 247 candidates and no public winner labels.
- `cluster_manifest.jsonl`: 3,000 task/run/parent records for split construction and clustered evaluation; it
  is not part of the model input surface.

Candidate fields are exactly `candidate_id_sha256`, complete `code`, `code_sha256`, canonical `operator`,
`step`, and `depth`. Operator is restricted to `Draft` or `Improve`; the 899 lowercase reconstruction
artifacts in blocked v1 were canonicalized without deleting candidates or changing code, labels, ordering, or
metadata. Explicit post-selection provenance fields are absent.

Only v2 may be used for training or future sealed evaluation. The adjacent v1 directory is retained as an
auditable failed release and remains blocked. Frozen/extension labels and the sealed vault are not included.
Do not replace or append to these files; publish any future revision under a new immutable directory.
