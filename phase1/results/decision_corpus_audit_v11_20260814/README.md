# Decision-Corpus Audit Protocol v1 — v11 result

Status: `INDEPENDENTLY_VERIFIED_DECISION_CORPUS_AUDIT`.

This artifact audits the nine released v11 decision-pair sets (train/frozen/extension × b0/b1/b2)
using only pair metadata and the card-to-physical-run map. It does not read card code, observations,
stdout, runtime, labels beyond the already released pair orientation/gap, or any prospective outcome.

## Main verified facts

- All supplied rows are true endpoint siblings from one reconstructed physical run. If a pruned parent
  is absent from the run map it is counted as an orphan; if it is present, its run must match.
- For b0, b1, and b2 independently, train versus frozen overlap is exactly zero for unordered pairs,
  endpoints, parents, and physical runs.
- Frozen b0 contains 1,498 pairs, 845 parent choice sets, 2,022 endpoints, 92 physical runs, and 22
  tasks. Exactly 751/1,498 pairs have `gap_raw < 1e-2` (`0.5013351134846462`).
- Train b0 contains 4,263 pairs, 2,293 parent choice sets, 5,499 endpoints, 333 physical runs, and 23
  tasks. Exactly 1,849/4,263 pairs are in the same hard region (`0.4337321135350692`).
- The audit reports rather than hides graph incompleteness: 805/845 frozen-b0 and 2,259/2,293
  train-b0 parent graphs contain every pair implied by the observed candidate set. It also reports
  pruned-parent counts and endpoint reuse.
- The independent verifier does not import the producer and reproduced every published aggregate for
  all nine pair sets after checking ten input hashes.

## Artifacts

- `audit_card.json`: machine-readable full metrics and input hashes.
- `DATASHEET.md`: compact human-readable table.
- `independent_verification.json`: independent recomputation receipt.

SHA-256:

- audit card: `623c6abedb2135297dec6130337486bca097ca6434cd6aed708d9723de9287bb`
- independent verification: `fa73be3d6404a58084f57741588e566aa846a948698ee9bdb05690d518a991d3`
- producer script: `c42c9177e937488841f47bbc9f9f04ee808219746b41e4adadf43804caa6f063`
- verifier script: `c25cd7ca53f4ec3faad8c84227c53bddc5d571ad813d9d1b35ad3d8ad48e8a5a`

## Interpretation boundary

This card verifies sampling-unit, choice-set, support, gap-composition, and split-isolation claims.
It deliberately does not recompute the independent regrade/noise ceiling, deployment query/init cost,
or prospective activation protocol. Those remain separately hashed attestations and must not be cited
as if this one program established them.
