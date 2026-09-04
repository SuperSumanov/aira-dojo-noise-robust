# Six-hour foreground session, 2026-09-05 Hong Kong

Requested: stay in this conversation and advance the current research for six hours,
checking the senior's new corpus. Window: 2026-09-04 17:53:04--23:53:04 UTC.
This file is a plan, not evidence that the full six hours have elapsed.

## Boundaries

- Entry HEAD 072a88ac0c3b6f931cc57b15f848110bed949444; fetched public direction first.
- G0 12377 is the only authorized GPU job. No new submit/retry, paid API, model fit,
  base-model update, checkpoint selection, or protected-cohort values/identities.
- G-reuse to L remains the candidate; source/config/experiment closure and an explicit
  fit budget are still required. The fixed-forward rewiring candidate remains closed.
- No rerun of completed DS stub or historical structure matrices to manufacture progress.

## Initial live checks

2026-09-04 17:53:46--47 UTC: G0 PENDING/Resources, runtime zero, source clean;
estimated start Hong Kong 2026-09-05 12:39:11, not guaranteed. Senior fetch succeeds,
HEAD b8d095180415957aa1bab31fa53ead1bba261c03 unchanged. Source archives 316,
physical runs 645, eligible runs 619, structural pairs 3910, endpoints 16844,
tasks 51, closure false, config-v2 sidecar names zero. LATEST:
bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456.
Intake PID 3884166 is dead following normal 145-poll completion at 07:04:03 UTC.

## Foreground intake design (announced before edit)

Add only a `--run-once` dispatch branch to the existing shell entry. Reuse its exact
constants, `verify_contracts`, `runner`, CPU interpreter, scientific/control sources,
credential-first intake and stability requirements. Do not initialize a monitor, change
the old PID or log, or spawn a background loop. Each invocation returns after at most
one original transaction. The conversation calls it no more often than every 300 seconds
within this window; no new invocation after its deadline. A transaction already begun
is allowed to finish atomically. Any failure stops subsequent automatic intake.

Validate the source diff mechanically against b20dd268 (only the dispatch insertion),
check shell syntax remotely, verify the installed original entry hash, clean control and
scientific commits, dead old PID, free lock and exact prior LATEST before the first call.
Record exit code, elapsed time and stdout/stderr hashes before reporting safe structural
fields. Never display raw error logs, archive payloads or protected values.

## Parallel work

Inspect the concrete missing caller integration between planned microbatches and the
new DS completion guard; implement only if it is a necessary, well-scoped prerequisite.
No new model loader/fit CLI or scientific parameter grid. Receive any new source package
through credential-first metadata checks before deciding how to validate it.

Progress will distinguish software correctness, corpus accrual and measured model effect.
