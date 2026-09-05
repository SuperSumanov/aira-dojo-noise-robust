# 0903 post-session maturity intake

Classification: `OUTCOME_BLIND_CORPUS_SNAPSHOT_ATOMICALLY_PROMOTED`.

The nine append-only `0903` archives were downloaded earlier but deliberately held until their
fixed six-hour maturity time, `2026-09-05T00:09:48.832417Z`. The original six-hour foreground
lease completed naturally after poll 64. A separately frozen successor wrapper was invoked once
at 00:10:05 UTC; there was no intake retry.

Accepted transaction:

- return code: 0; elapsed: 150.19056317210197 seconds;
- LATEST: `76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285`;
- accumulator summary SHA-256:
  `71907e82a8c3f8ffb6d88c54766725f44f672f97e04de1caa4e0ed8d37a991c0`;
- wrapper receipt SHA-256:
  `605af92b0132a33ceca8798f8aca482f0e9f82405e13c4399802c6e16446ff92`;
- source archives: 325; drops: 167;
- physical runs: 645 to 649; eligible runs: 619 to 623;
- eligible endpoints: 16,844 to 16,925; structural pairs: 3,910 to 3,919;
- eligible tasks: 51 to 51; first-960 remaining: 337; closure: false.

Independent safe postcheck required exact LATEST/summary/receipt bytes, one completed poll root,
no FAILED marker, snapshot mode 700, summary/LATEST mode 600 and receipt mode 400. All 18 entries
in the snapshot `SHA256SUMS` verified. The runner status is
`PROSPECTIVE_ARCHIVE_TRANSACTION_COMMITTED`; label-vault open is false, outcome/prediction files
opened are empty, stream credential-shape hits are zero, and no private identity/value was emitted.

Two inline SSH verification attempts were incorrectly expanded by local PowerShell before a
usable remote check was obtained. Neither is counted as evidence. The accepted fixed postcheck
script SHA-256 is `6cc93424c268b3709c88c21c3ca3bcaafa77bde604fabad3093b03bd4c1e5556`.

The nine archives adding only four eligible runs is an observed acceptance result, not an error
to be replaced by archive count. No protected label, prediction, accuracy, utility or identity
was shown; GPU jobs, API calls and model fits were zero.
