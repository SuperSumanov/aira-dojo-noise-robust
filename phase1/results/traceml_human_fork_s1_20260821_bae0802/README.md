# TraceML human-fork future transfer：S1 formal decision

Status: `IDENTITY_OR_JOIN_AMBIGUOUS`. Source commit:
`bae0802895214851983fa99eee784e651648d384`. The fixed graph contains 134 competitions and the 141-entry
manifest joins without a missing direction; exactly seven manifest entries are unused. The graph identity itself does not
meet the frozen contract:

- 4,674 / 174,558 node rows do not join to `kernels.parquet` on both kernel ID and competition;
- 906 / 174,558 node rows do not join to `trees.parquet` on both tree ID and competition;
- 6 / 409 canonical fork nodes disagree with their parent on tree/competition;
- 403 / 409 fork nodes pass the local parent/depth/first-version checks, and all 403 canonical edge triples occur exactly
  once in `edges.parquet`, but the pre-registered contract does not permit filtering down to them post hoc.

Consequently `identity_and_direction=false`. Neither implementation opened `best_private_score` or `score_public`; no
support aggregate, predictor score, effect metric, notebook content, GPU, or API was used. The 2.9GB raw archive was not
downloaded and S2/S3 are closed. This is a dataset-join eligibility failure, not evidence against the frozen transition
scorer or the AIRA strict-future estimand.

Formal integrity: producer x2 and independent verifier x2 were byte-identical; focused tests were 9 passed and the full
phase suite was 591 passed with 25 warnings. The 52-file remote manifest, forbidden-path count (zero), credential scan
(zero), and read-only check all passed. Compact evidence here has SHA-256:

- `summary.json`: `df469bbdc93df1f7130fa9a336c1f45e3f3338f881ef5f5313b6470b9aac78c2`;
- `independent_verification.json`: `21f4c5e1de9463623e4633f3f225c86078a533ebbab7783a8fee09adefadfee2`;
- remote full manifest: `15884d9d33319d94ee138d61d79d983d599482e487773a9292df636d203deed5`.

The first pre-read attempt at commit `878e719...` was interrupted before producer launch because the regression environment
had not explicitly capped BLAS/OpenMP threads. Its separate remote directory is sealed as
`ABORTED_BEFORE_GRAPH_READ_THREAD_OVERSUBSCRIPTION`. The formal rerun pinned all CPU thread pools to one. Producer wall
time was 26.21 seconds with maximum RSS 455,716KB, so the preflight's `<100MB` estimate was incorrect even though the run
remained CPU-only and small enough for the host.

Full immutable artifacts:
`/research/d7/spc/yzyang4/external-audits/traceml-human-fork-s1/bae0802-v1`.
