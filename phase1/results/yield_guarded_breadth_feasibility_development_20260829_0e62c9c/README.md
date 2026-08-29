# Yield-Guarded Breadth Feasibility v2 development package

This package records a post-readout, historical development result. It is not external confirmation.

- `aggregate_result.json`: aggregate-only A/B-byte-exact solver output.
- `independent_aggregate_verification.json`: non-importing aggregate gate recomputation; it does not reconstruct the private witness.
- `development_receipt.txt`: single-CPU A-run receipt.
- `ab_receipt.txt`: fresh B-run byte-exact receipt.
- `independent_receipt.txt`: fresh Linux aggregate verifier receipt.
- `v1_thread_preflight_violation.txt`: preserved no-readout v1 stop evidence.
- `self_test.txt`: legal synthetic/exhaustive/infeasible controls.
- `time.txt`: A-run wall/CPU/RSS receipt.

Remote roots:

- v1 stopped: `/research/d7/spc/yzyang4/yield-guarded-breadth-development/dev-87ba919-r1`;
- v2 A: `/research/d7/spc/yzyang4/yield-guarded-breadth-development/dev-0e62c9c-r2`;
- v2 B: `/research/d7/spc/yzyang4/yield-guarded-breadth-development/dev-0e62c9c-r3-ab`;
- independent aggregate verification: `/research/d7/spc/yzyang4/yield-guarded-breadth-development/independent-aggregate-v2`.

Exact code/preflight/result/verifier/verification hashes are recorded in `phase1/实验记录/2026-08-29/YieldGuardedBreadthFeasibility_v2_开发裁决.md` and bound by `SHA256SUMS`.
