# 0823 LMSYS structural rejection

This immutable registry settles exactly
`0823/lmsys-chatbot-arena-8seeds.tar.gz` at SHA-256
`31c53f6027b39847149506135649a2c48a5c5feb30396b2d0e78f58341bd9661`.

The credential-first, outcome-blind audit found four checkpoint journals. None
identifies a competition from within the archive. The archive is therefore rejected
as a whole under `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE`; no filename
inference or partial-run salvage is allowed.

The formal audit and registry build were each executed twice at source commit
`5d0baaddca14ce6db53a43ed1976b85a8b24c9f3`; both pairs were byte-identical. The
remote receipt is rooted at
`/research/d7/spc/yzyang4/preflight-0823-lmsys-rejection/5d0baad-v1`, whose
`SHA256SUMS` hash is
`fe1f2f508329874b12745937d3a3ec0ad30b6dd33a74a6bcc6b6751ead1cdc2b`.

The earlier four-archive batch wrapper v1 is retained as a failed attempt because it
did not enter the repository before invoking the audit module. Its corrected v2
audit independently established that Alaska, RANZCR, and TensorFlow Speech satisfy
the exact-one task-identity rule, while LMSYS does not. No outcome, label, score,
prediction, GPU job, API call, or model fit was used.
