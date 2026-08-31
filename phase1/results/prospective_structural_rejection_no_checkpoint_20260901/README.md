# 0830 no-checkpoint archive structural rejection

The append-only intake committed four new archives and then stopped at poll 14 before
any later archive could be skipped. The bound archive produced no physical runs.

The frozen producer A/B and a separately implemented raw-tar verifier A/B agree that
the archive contains 2 discovered run roots, both live-only, and zero checkpoint
journals. The independent verifier read zero journal-member bytes and found zero
credential-shaped member names. The immutable rejection reason is therefore
`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS`.

The failed attempt remains retained. This is an outcome-blind structural disposition,
not a statement about labels, predictor accuracy, search utility, or method effect.
