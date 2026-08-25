# 0823 AI4Code structural rejection

This immutable registry settles exactly
`0823/AI4Code-8seeds.tar.gz` at SHA-256
`cecac2bc9f156c33630f7e4bd740f4e403907aa656fd740a2e3b2ad6af804a14`.

The credential-first, outcome-blind audit found four checkpoint journals. Three
identify exactly one competition and one identifies none. The archive is therefore
rejected as a whole under
`JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE`; no filename inference or
partial-run salvage is allowed.

The formal audit was executed twice and the registry was built twice at source commit
`5d0baaddca14ce6db53a43ed1976b85a8b24c9f3`; both pairs were byte-identical. The valid
v2 remote receipt is rooted at
`/research/d7/spc/yzyang4/preflight-0823-ai4code-rejection/5d0baad-v2`, whose
`SHA256SUMS` hash is
`6c8ab9b301c16dec1c025b7ef1fe49c092d4f9b24bbad3b9506e8adb06cd7c7a`.

The v1 wrapper is retained as a failed attempt: its credential scan included its own
output file, so that scan was invalid even though the scientific audit matched v2.
No outcome, label, score, prediction, GPU job, API call, or model fit was used.
