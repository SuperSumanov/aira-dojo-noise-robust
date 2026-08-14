# Label repeatability attestation v2

- Status: `VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2`
- Usable cards: 207
- Measured tasks: 10
- Original-vs-first-repeat pair observations: 3017
- Raw original-vs-first-repeat agreement: 0.965860125953
- Task-macro original-vs-first-repeat agreement: 0.980180828387
- Predictor ceiling measured directly: no

The inferred single-label quantity requires the independent, exchangeable, symmetric-error model stated in `attestation.json`.

| target | pairs | measured-task share | repeat agreement | inferred single-label accuracy | extrapolates tasks |
|---|---:|---:|---:|---:|---|
| extension:b0 | 136 | 0.757353 | 0.929877 | 0.959914 | true |
| extension:b1 | 39 | 0.846154 | 0.913706 | 0.951241 | true |
| extension:b2 | 30 | 0.900000 | 0.926781 | 0.957545 | true |
| frozen:b0 | 1498 | 0.732977 | 0.913431 | 0.948825 | true |
| frozen:b1 | 323 | 0.628483 | 0.891694 | 0.936185 | true |
| frozen:b2 | 265 | 0.656604 | 0.882473 | 0.931465 | true |
| train:b0 | 4263 | 0.680038 | 0.940036 | 0.965515 | true |
| train:b1 | 861 | 0.595819 | 0.927779 | 0.958683 | true |
| train:b2 | 692 | 0.624277 | 0.924661 | 0.956999 | true |

Primary uncertainty is a 2,000-repetition task-cluster bootstrap. Pair-i.i.d. binomial intervals are not used.
Duplicate `(card, rep)` successful records are retained in the primary physical-record estimand and audited with first/last sensitivity modes.
