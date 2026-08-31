# Prospective intake no-checkpoint repair — 2026-09-01

This package records the safe deployment receipt for control commit
`b20dd2682d609c0236c138c08797678cf31a2fc0`. The immutable structural-rejection
registry had already passed producer/verifier A/B and independent verification.

The first deployment attempt stopped before tests because a zero-hit credential
scan returned grep rc=1. The second kept the same worktree and test set but was
interrupted after a synthetic GBM unit-test section showed pathological CPU thread
oversubscription. The third fixed only the BLAS/OpenMP thread ceilings, passed 23
focused and 1,893 full tests, and started the monitor. A Bash PID assertion typo
occurred after start; the read-only v4 post-deploy verifier therefore checked the
already-running PID, exact command line, clean commit, script/registry hashes, and
first successful poll without restarting it.

No label, outcome, prediction, accuracy, utility, candidate identity, or private
profile was read. GPU/API/model experiment/base-model update were all zero.
