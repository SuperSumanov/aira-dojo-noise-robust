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

All hashes below use the explicit `normalized_utf8_lf_v1` text-hash contract (CRLF and bare CR are
converted to LF; final-EOL presence is preserved). This avoids `core.autocrlf` changing an otherwise
identical release card between Windows and Linux.

SHA-256 (values regenerated after the hash-contract correction):

- audit card: `a3b5e12cbe280909300d83d54a326c06c736cfb59f2f6762cb5518720393b399`
- independent verification: `63497b5faccc6657cbf58be885a12548c6b16ec15a19cb598c02bb2192ef4a92`
- producer script: `53117eaf27773f78e07073a3cd4b7aa85610881805ce77b5fe62432be1212dda`
- verifier script: `cc7284332a5442e9f25769c60d37a5dc0158d697e601d3d3cd824553dba3be59`

## Interpretation boundary

This card verifies sampling-unit, choice-set, support, gap-composition, and split-isolation claims.
It deliberately does not recompute the independent regrade/noise ceiling, deployment query/init cost,
or prospective activation protocol. Those remain separately hashed attestations and must not be cited
as if this one program established them.
