# Decision-corpus audit card

- Protocol: `decision_corpus_audit_v1`
- Status: `VERIFIED_DECISION_CORPUS_AUDIT`
- Raw code/observations read: no

| Pair set | pairs | parents | endpoints | runs | tasks | hard share | complete parents |
|---|---:|---:|---:|---:|---:|---:|---:|
| extension:b0 | 136 | 114 | 239 | 15 | 10 | 0.507353 | 114 |
| extension:b1 | 39 | 37 | 75 | 10 | 7 | 0.589744 | 37 |
| extension:b2 | 30 | 28 | 57 | 6 | 4 | 0.566667 | 28 |
| frozen:b0 | 1498 | 845 | 2022 | 92 | 22 | 0.501335 | 805 |
| frozen:b1 | 323 | 229 | 507 | 42 | 20 | 0.662539 | 224 |
| frozen:b2 | 265 | 180 | 404 | 27 | 17 | 0.690566 | 176 |
| train:b0 | 4263 | 2293 | 5499 | 333 | 23 | 0.433732 | 2259 |
| train:b1 | 861 | 597 | 1325 | 140 | 22 | 0.545877 | 594 |
| train:b2 | 692 | 466 | 1044 | 105 | 21 | 0.589595 | 464 |

## Same-budget train/frozen isolation

| budget | pair overlap | endpoint overlap | parent overlap | run overlap | pass |
|---|---:|---:|---:|---:|---|
| b0 | 0 | 0 | 0 | 0 | true |
| b1 | 0 | 0 | 0 | 0 | true |
| b2 | 0 | 0 | 0 | 0 | true |

Label-noise ceilings, deployment-time/cost semantics, and prospective activation are deliberately separate attestations; this card must not be cited as having recomputed them.
