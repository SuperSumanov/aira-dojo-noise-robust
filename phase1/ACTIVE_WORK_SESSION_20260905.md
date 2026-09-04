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

## New senior drop discovered and bounded synchronization

The old mirror was stale rather than the source being unchanged. A bounded, metadata-first
listing of the Google Drive root found nine files under the plain date directory `0903` and
zero local counterparts. The check did not traverse or download `checkpoint` or `mlebench`.
An earlier whole-root metadata attempt hit its fixed request ceiling and failed closed; its
partial directory was preserved and was not used as a source manifest.

After a written preflight and a clean-code commit, an exact-nine synchronizer downloaded and
atomically promoted only those nine compressed archives. It reserved and released its own
1 GiB quota probe, retained fresh local modification times, did not extract/decompress/read
members, did not overwrite the existing 316 archives, and did not load protected values,
models, GPUs, or paid APIs. Verified outcome:

- 9 new archives; 299168545 compressed bytes; 22 HTTP requests; 73.9418 seconds;
- source archive count 316 to 325;
- private exact-nine manifest SHA-256
  `e048e074ea70ae78c17d37f4ad49cac76aad0fd7d4e19caa876928e295962377`;
- all nine satisfy the six-hour age gate no earlier than
  `2026-09-05T00:09:48.832417+00:00`;
- therefore they are downloaded but not yet intake-eligible during the originally fixed
  six-hour window ending `2026-09-04T23:53:04+00:00`.

No eligibility or corpus statistic is incremented before the original credential-first,
stability, trace/security, independent-verifier and atomic-promotion transaction succeeds.
Foreground checks continue to record safe structural receipts only.

Local full-suite collection was attempted after these documentation changes and stopped with
11 import errors because the Windows Python lacks SciPy/scikit-learn; no test body ran and no
scientific assertion failed. The focused foreground-intake suite remains 4/4 passing. A clean
Linux export with the established dependency environment is required before publication.

One subsequent read-only `rg` status search was scoped to the whole `phase1` directory and
matched two historical v11 Cards rows plus old result rows, producing excessive historical
content. It did not touch prospective vaults or drive any selection, fit or scientific
conclusion, but it repeated a previously documented search-scope mistake. All later searches
must use explicit source/report/code paths and exclude Cards/data/result payloads.

## Independent Linux protocol regression

At scientific commit `06d868a1a43b2f1b86254790c4de21fafefb4903`, a final explicit,
data-free dependency archive with SHA-256
`00f2a417127d413ac4226b068f6533a713660e3077fb1f193daae16cbeedfd78` produced
`118 passed, 1 skipped` in the independent Linux environment. The skipped check is the
existing opt-in CPU torch autograd test. Two broad archive attempts stopped before tests on
already documented historical LFS 404s; the first narrow attempt had one missing source
dependency and is also retained. This validates protocol software only and does not alter
the source/G0/GPU block or constitute a model-effect result.

## Target-local contrast variance result

A new result-blind protocol was frozen and pushed before any variance readout. The first
formal root stopped at pytest collection because one test dependency was omitted. The second
stopped in pytest because raw-byte JSON hashes differ across LF/CRLF checkouts; this was
corrected to canonical-JSON hashing and pushed before data access. Both roots are retained.

At corrected commit `7650c48adfaa184a32b0c615ccd106abc586e0be`, formal v3 completed
producer A/B and an independent grounded-Laplacian verifier A/B. All 23 focused tests and 42
manifest entries pass, stderr is empty, and 531 numeric values agree within
`3.3306690738754696e-16`. The frozen overall status is NOT_SUPPORTED: spectral50 improves
pair-weighted local-target variance over cheapest/hash by only about 1.49%/1.54%, below the
3% gate; pooled p90 is unchanged at 1.0; and cheapest-control gain concentration is 23.78%.
Broad task-level improvements are descriptive only and do not rescue the failed gates.

The first formal record-consistent sensitivity attempt at source commit `fe9aec1` failed
closed before producing metrics: `producer_a` returned a `KeyError`, stderr was empty,
and no B run or verifier was started. Diagnosis found that the new caller expected an
explicit `reuse_pairs` count that the already-tested task summarizer intentionally does
not return. Gates and inputs were unchanged; the fix adds an explicit count-binding helper
and an integration regression test before any retry. The failed root is preserved.
