# Outcome-blind intake natural-completion renewal v3 — frozen preflight

Date: 2026-09-02. This is CPU-only maintenance of the existing append-only intake,
not a scientific experiment and not a result-unblinding action. Nominal monitor ETA
is 43,500 seconds (145 fixed polls at 300 seconds); the first-poll deployment gate is
expected within 90 seconds.

1. **Direction.** `CURRENT_DIRECTION.md` 0L0q remains authoritative. HCE,
   multi-fidelity, Probe, score-channel, and K>=1 lookahead remain closed.
2. **Objective.** Start exactly one additional fixed monitor cycle after a normal
   145-poll completion; no metric or result-dependent stopping exists.
3. **Revision.** Control commit is
   `b20dd2682d609c0236c138c08797678cf31a2fc0`; installed monitor SHA-256 is
   `ef658449...8eead`; the control worktree must be clean.
4. **Inputs.** Baseline is 296 stable archive paths, LATEST `bf7674a4...ce0d6`,
   summary `5c00320b...50b6f`, and 559 provisional first-960 runs.
5. **Estimand.** None changes. The monitor only maintains the frozen structural
   accumulator and never computes accuracy, utility, or a search result.
6. **Leakage/security.** Label vault, outcomes, prediction values, candidate profile,
   and private selection remain closed; installed intake stays credential-first.
7. **Resources.** CPU-only; GPU/paid API/model-fit/base-update=`0/0/0/0`.
8. **Environment.** Exact control worktree, commit, script hash, PID, runner lock,
   LATEST, source count, log hash/bytes/lines, and completion count are preconditions.
9. **Determinism.** Archive order and all monitor configuration remain unchanged;
   the pre-existing log must remain an exact byte prefix after launch.
10. **Failure.** Any drift, duplicate result root, live old PID, occupied lock, or
    first-poll nonzero result exits fail-closed and kills only the newly created PID.
11. **Stop/receipt.** The installed monitor stops after 145 fixed polls. Deployment
    is accepted only after first poll rc=0, independent verification, and immutable
    safe receipt; previous evidence is never overwritten.
