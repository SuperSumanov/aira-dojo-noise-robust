# Critic component static suite — compact evidence

Formal status: `STATIC_SUITE_INDEPENDENTLY_VERIFIED_NO_STRONG_ADVANTAGE`.

This directory is the Git-sized evidence bundle for the preregistered CPU-only static-feature suite at source commit
`76c1b49422ed444ac2aaa43612e80e6261584acd`. The complete immutable artifact remains on the cluster at:

`/research/d7/spc/yzyang4/critic-component-static-suite/76c1b49_20260821T022057Z`

Key result: dev selected `static_gbm_task`; frozen same-pool test micro=`0.560687432867884`, task macro=
`0.5585685275472433`, task-clustered 95% CI=`[0.500809682553181,0.6176416031350442]`, parent-clustered
95% CI=`[0.5228966986155484,0.5984075062159282]`. The positive claim against chance passes, but the preregistered
claim against fixed same-pool TF-IDF fails: paired task delta=`-0.01722973871137726`, CI=
`[-0.11177361183157879,0.09201062529949726]`; paired micro delta=`-0.010741138560687433`, parent CI=
`[-0.06271933251042952,0.04004332013926007]`.

Independent full-refit verification did not import the producer and reproduced pair/task/parent/summary values with maximum
absolute difference 0.0. Producer×2 and verifier×2 were byte-identical; all 35 sealed manifest entries passed SHA-256,
the recursive file set was exact, all six diff/stderr files were empty, the result tree was read-only, and credential-shape
scans were zero. GPU/API usage was zero.

A post-seal, single-thread full regression at the same source commit passed `550` tests with `25` deprecation warnings;
the compact receipt records the intentionally terminated first launch whose BLAS runtime expanded to about 30 CPU threads.
Neither postvalidation launch modified the read-only scientific artifact.

Files:

- `metrics.json`: compact machine-readable metrics and gate outcomes;
- `final_verification_receipt.json`: exact independent-verifier receipt;
- `combined_conclusion.json`: exact final status receipt.
- `input_sha256.txt`, `software_cpu_receipt.txt`, `preflight_matrix.txt`: exact bound inputs, software/CPU
  environment, and frozen execution matrix copied from the sealed artifact (`software_cpu_receipt.txt` is a
  filename-safe copy of sealed `environment.txt`).
- `postvalidation_receipt.json`: full-suite result, hashes, and the preserved resource-hygiene abort receipt.

Full interpretation and limitations:
`phase1/实验记录/2026-08-21/CleanDirectDecision_component同池静态suite_正式裁决.md`.
