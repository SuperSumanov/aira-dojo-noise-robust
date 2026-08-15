# Score-channel prospective eligibility refresh

Date: 2026-08-16 (Asia/Hong_Kong). Status:
`VERIFIED_100_RUNS_INSUFFICIENT`.

This is an outcome-blind run-gate refresh, not a score-channel effect result. It reads
only immutable production transactions plus intake `summary.json` and
`source_provenance.json` files produced by the credential-first intake. It does not
open environment members, raw journals, code, stdout, scores, outcomes, frozen labels,
or the label vault.

## Recovery and frozen input

The 0814 intake monitor originally stopped fail-closed on
`tweet-sentiment-extraction-8seeds.tar.gz`: all eight checkpoint journals lacked a
competition ID. The control-layer amendment at commit
`df00f2655af9d5d47b72ca4fd2c247222f2ac1d4` binds that single rejection to exact path,
size, mtime, full archive SHA, fixed reason code, and diagnostic receipt. It does not
infer the task from the filename and creates no scientific transaction for that archive.
The unchanged intake, scorer, registry validator, and accumulator remain pinned to
scientific commit `90842c49dbd73d41d405a5ecdad2224ee447b375`.

Cluster tests passed 338/338 before recovery. Five later structurally valid archives
then committed successfully. The next poll reported:

```
archives=145 baseline=128 ready=0 rejected=1 transactions=16 outcomes_read=false
```

The final immutable production snapshot is
`87a137a4f086b7dba767aebd754722802f7af284830a4b22f37c4476f6bef5e2`.
Safe sidecars from exactly those 16 transactions were copied into a race-checked frozen
snapshot before the run registry was rebuilt.

## Formal result

The producer ran twice with mechanism commit
`4c964f8691b00af2f5ecb98f7a60dcd272bfb8cc`, `min_runs=150`, and
`max_dominant_task_share=0.25`. The two `eligible_runs.jsonl` files and two
`summary.json` files were byte-identical. A separate verifier that does not import the
producer independently reconstructed every eligible row and gate field.

| quantity | verified value |
|---|---:|
| safe intakes | 16 |
| unique post-mechanism physical runs | 100 |
| tasks | 13 |
| dominant task runs | 16 |
| dominant task share | 0.16 |
| remaining to 150 | 50 |
| task-balance gate | pass |
| 150-run gate | wait |
| replay authorized | false |

Per-task physical-run counts are:

| task | runs |
|---|---:|
| aptos2019-blindness-detection | 3 |
| dog-breed-identification | 8 |
| dogs-vs-cats-redux-kernels-edition | 16 |
| learning-agency-lab-automated-essay-scoring-2 | 8 |
| new-york-city-taxi-fare-prediction | 6 |
| random-acts-of-pizza | 4 |
| ranzcr-clip-catheter-line-classification | 12 |
| text-normalization-challenge-russian-language | 8 |
| tgs-salt-identification-challenge | 8 |
| tweet-sentiment-extraction | 3 |
| us-patent-phrase-to-phrase-matching | 8 |
| ventilator-pressure-prediction | 8 |
| whale-categorization-playground | 8 |

Artifact hashes:

- safe-sidecar snapshot receipt:
  `df036b1e69fb944bc3c3037cc01b34e464346c118c324c427b6ffe8da562183d`;
- eligible runs:
  `71b8f3f0710e5a6018c7db3a845a19e285b408473d61542fb5c6086da9cc9f66`;
- producer summary:
  `5f713940fac313ad69f0731c421d60cee51155c06b60f0d68b0d89e89fff2efd`;
- independent receipt:
  `5aad3684876e096198f9363cdaded806664473796a4750ec59ec43e8afdf88fb`.

Remote artifacts:

- `/research/d7/spc/yzyang4/score-channel-safe-sidecars-df00f26-20260816-a1/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-df00f26-20260816-a1/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-df00f26-20260816-a2/`;
- `/research/d7/spc/yzyang4/score-channel-eligibility-df00f26-20260816-independent.json`.

## Interpretation

The positive result is operational and dataset-facing: the rigorously usable prospective
cohort grew from 47 to 100 physical runs while task balance stayed safely inside the
fixed 25% cap. This materially de-risks the planned confirmation and leaves 50 runs,
instead of 103, before the trusted parent gate can open. It is not evidence that the
external submission score beats stdout; that claim remains sealed until the fixed
150-run gate passes, the parent selector emits its receipt, and the user approves the
exact replay matrix and GPU budget.

Resources used here: CPU only; GPU 0; API 0; base-model updates 0.
