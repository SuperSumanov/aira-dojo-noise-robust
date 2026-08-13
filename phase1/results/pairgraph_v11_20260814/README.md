# Pair-graph intervention v11 result

Protocol `pairgraph_v11_train_oof_descriptive_v1` ran at commit
`926db4a3ece3fc24a2714b50e23b76c64b270c5c`. Producer and independent verifier agree on
`VERIFIED_PAIRGRAPH_EFFECT_NOT_SUPPORTED`; `frozen_read=false`.

On 3,921 common-support sibling rows and 20 tasks, char-TFIDF task-macro accuracy was 0.5284907717433142
on real siblings, 0.5814158858170438 under task/fold-matched uniform cross-run pairing, and
0.5478674917657668 after also transporting the frozen gap bins. The total +0.052925114073729684 had a
task-bootstrap 95% CI of [-0.04418436017058699, 0.15460114273445769]. Only two of four arms had a positive
point effect and none had a positive CI lower bound, so the preregistered universal-inflation gate failed.

The descriptive model ranking nevertheless changed: static LR led on siblings, while char-TFIDF led on both
cross-run graphs. This is retained as a benchmark interaction, not as a confirmatory or causal claim.

Files:

- `summary.json`: SHA-256 `56b84e51430ad706ef00c5a048e5d6aa6effbdf037f05c078fe5a5c960b30607`;
- `independent_verify.json`: independent full re-enumeration;
- `stratum_stats.csv`: SHA-256 `1fd3667d19a703a63686b9f54eb2256251e82b85b4e9c6a091077dec59e8c266`;
- `per_task.csv`: SHA-256 `13c394bbca697a2b07c04c0b2a6cd31051d535931f6378ecf3fe161cb28f245c`;
- `full_artifacts.tar.gz`: SHA-256 `5d75dc403cbe866b749e798947147b03cf248d003119da101a10fbfc2ffc675e`,
  60,636 bytes.

The remote manifest verified all 18 payload files; secret-pattern and suspicious-filename scans were zero.
