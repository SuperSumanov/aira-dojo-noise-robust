# Balanced-continuation E0 assignment replay

Status: `VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT`.

This is a zero-GPU, zero-API engineering result, not evidence that the proposed method improves
search. At exact commit `4ff44dd99ba4848db1b039cc2383c2114793a379`, the cluster passed
34 tests and all 13 preflight checks, then produced and independently reconstructed a synthetic
blocked assignment with four anchors, three siblings per anchor, two replicates per sibling,
and horizon two. All 24 rollout jobs contain exact equal-K support; the 24 warm starts plus 48
continuation executions give 72 planned synthetic candidate executions.

The producer and replay assignment manifests were byte-identical. The archived assignment
manifest SHA-256 is
`122628cc49f92a22aeb9acbdacee3ea18828b10edabc665d655c8aa930e5a726`.
Both independent receipts report no outcomes and exact reconstruction. Real GPU E1/E2
collection remains behind its previously documented budget gate.
