# Score-channel prospective eligibility refresh

Date: 2026-08-17 (Asia/Hong_Kong). Status:
`VERIFIED_138_RUNS_INSUFFICIENT`.

This is an outcome-blind run-gate refresh, not a score-channel effect result. It reads
only immutable production transactions plus intake `summary.json` and
`source_provenance.json`. It does not open environment members, raw journals, code,
stdout, scores, outcomes, frozen labels, or any label vault.

## Frozen input and security

The production runner committed six new structurally valid 0815 archives, increasing
the immutable transaction count from 16 to 22. A seventh archive,
`text-normalization-challenge-russian-language-8seeds.tar.gz`, was rejected before
scientific intake because all 8/8 checkpoint journals lacked a competition ID. Its
rejection is bound to exact path, size, mtime, full archive SHA-256, fixed reason code,
and a credential-first diagnostic receipt. The earlier malformed 0814 tweet archive
remains bound to its original immutable rejection registry.

The latest production snapshot is
`3a14af8b0c661920e050c1a6692a9f5780e54ee80d80b6b55d82d7a8a0a2690d`, and its
transaction registry SHA-256 is
`e338538a7d57cb654847154eef7cb0f80ed09489694bca64e77ffb22f26c4138`.
Exactly two safe files per intake were copied into a race-checked snapshot:
`summary.json` and `source_provenance.json`. The snapshot receipt records
`label_or_outcome_files_copied=false`.

Resources: CPU only; GPU 0; API 0; base-model updates 0. Replay authorization remains
false regardless of this refresh result.

## Formal result

The unchanged eligibility producer ran twice with mechanism commit
`4c964f8691b00af2f5ecb98f7a60dcd272bfb8cc`, `min_runs=150`, and
`max_dominant_task_share=0.25`. Both `eligible_runs.jsonl` files and both `summary.json`
files were byte-identical. A separate verifier that does not import the producer
independently reconstructed every eligible row and gate field.

| quantity | verified value |
|---|---:|
| safe intakes | 22 |
| unique post-mechanism physical runs | 138 |
| tasks | 16 |
| dominant task | ranzcr-clip-catheter-line-classification |
| dominant task runs | 19 |
| dominant task share | 0.13768115942028986 |
| remaining to 150 | 12 |
| task-balance gate | pass |
| 150-run gate | wait |
| replay authorized | false |

Per-task physical-run counts are:

| task | runs |
|---|---:|
| aptos2019-blindness-detection | 3 |
| cassava-leaf-disease-classification | 4 |
| dog-breed-identification | 15 |
| dogs-vs-cats-redux-kernels-edition | 16 |
| facebook-recruiting-iii-keyword-extraction | 4 |
| google-quest-challenge | 8 |
| learning-agency-lab-automated-essay-scoring-2 | 8 |
| new-york-city-taxi-fare-prediction | 6 |
| random-acts-of-pizza | 4 |
| ranzcr-clip-catheter-line-classification | 19 |
| text-normalization-challenge-russian-language | 8 |
| tgs-salt-identification-challenge | 8 |
| tweet-sentiment-extraction | 3 |
| us-patent-phrase-to-phrase-matching | 8 |
| ventilator-pressure-prediction | 16 |
| whale-categorization-playground | 8 |

Artifact hashes:

- safe-sidecar snapshot receipt:
  `367557a7d67ec5f3c99904e1fb6849393b968e0133cbcc85e1a95ecde29b648a`;
- eligible runs:
  `5876f6eb091dbfc5386978dab0bf11b515c9c5fa85035d07dbfa3d7498ae1855`;
- producer summary:
  `e6d95b75583122343f957ed667ba5ee9b17a89e268b5088aea42da17c2bd0648`;
- independent receipt:
  `2755046c9bbdeb06ab045f9f430e9617fd1add17e2d5aac5b15bc8dd4b7c3362`.

Remote artifacts:

- `/research/d7/spc/yzyang4/score-channel-safe-sidecars-7a4c3ee-20260817-a1/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-7a4c3ee-20260817-a1/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-7a4c3ee-20260817-a2/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-7a4c3ee-20260817-independent.json`.

## Interpretation

The rigorously usable prospective cohort grew by 38 physical runs while the fixed task
balance gate remained comfortably inside 25%. This materially reduces the outstanding
gate from 50 to 12 runs. It is not evidence that the external submission score beats
stdout: that effect remains sealed until at least 150 eligible runs exist, the trusted
parent selector is verified, and the user approves the exact replay matrix and GPU
budget. No optional stopping or early replay is allowed.
