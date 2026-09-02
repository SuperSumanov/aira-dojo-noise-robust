# Decision Corpus Reproducibility and Audit Appendix — Internal Draft

> Status: manuscript appendix draft, 2026-09-02. This document follows
> `CURRENT_DIRECTION.md` and Evidence Index v10. It does not authorize opening any
> prospective label, outcome, prediction value, candidate identity, or private
> selection profile. Bracketed one-shot outputs remain sealed until the frozen
> first-960 identity cohort and independent accrual-closure receipt both exist.

## A.1 Reproduction levels and access boundary

Decision Corpus separates four reproduction levels so that an apparently benign
verification command cannot silently broaden access.

| Level | Inputs that may be opened | Permitted output | Forbidden inference |
|---|---|---|---|
| L0: metadata-only | release descriptors, LFS pointers, filenames, sizes, hashes, schema paths, structural receipts | inventory, hash closure, row/run/task counts | label quality, predictor performance, candidate identity |
| L1: historical public audit | immutable historical cards/decision resources and declared public aggregates | lineage, split, noise, cost, weighting, release-governance receipts | prospective generalization or search utility |
| L2: sealed prospective maintenance | append-only archive registry, structural manifests, prediction-receipt hashes, closure markers | value-free support and continuity receipts | prediction values, labels, accuracy, utility, private selection profile |
| L3: one-time confirmation | exact frozen identity anchor, prediction escrow, label vault, closure receipt | preregistered aggregate Table 4B and robustness views | checkpoint selection, cohort reselection, threshold rescue, row-level disclosure |

Every executable declares its level. A verifier must reject an undeclared input,
an input whose hash differs from the protocol, or an attempt to cross from L0--L2
to L3 without the one-time closure anchor.

## A.2 Immutable inputs and rebuild contract

Historical v11 is defined by the release descriptor and ordered batch registry,
not by whichever files happen to be present in a working directory. The rebuild
contract fixes:

1. ordered immutable batch paths, LFS object IDs, byte sizes, and SHA-256 values;
2. deterministic concatenation and physical-run reconstruction rules;
3. the endpoint-to-run map used when a decision row lacks an explicit `run_id`;
4. the nine decision-resource roles and their expected row/hash manifests; and
5. a release receipt that binds the generated artifact to the exact source commit.

The current v11 release contains 29 batches and 16,012 cards. Its nine decision
resources contain 8,107 direct-sibling rows under recorded parent pointers. The
strict parent-present core has 7,579 rows; 528 lineage-verifiable orphan-parent
rows remain a separately reported tier. These counts are properties of the pinned
release, not estimates from a sampled subset.

Rebuild implementations must write a fresh output and compare it byte-for-byte with
the claimed artifact. They must not edit an immutable batch or overwrite a failed
formal root. Any sanitized release is an append-only successor with a new descriptor.

## A.3 Unit definitions and relation construction

The hierarchy is:

```text
archive -> physical run -> endpoint/card -> recorded parent -> sibling fragment
```

- An **archive** is one immutable uploaded search artifact.
- A **physical run** is one agent-search execution, identified from source journals
  when available and otherwise by the documented deterministic segmentation rule.
- An **endpoint/card** is a retained candidate program with its execution record and
  search context.
- A **decision parent** is the recorded parent shared by retained children from the
  same physical run.
- A **numeric sibling pair** orients two finite-grade children of that parent.
- A **status-certified edge** records validity dominance separately from continuous
  numeric quality. Unknown relations stay unknown.

The released unit is therefore a sibling **fragment**, not a complete counterfactual
choice set. `C(n,2)` is declared capacity among retained children and must not be
described as a log of comparisons actually made by the agent. Recorded parent pointers
are auditable lineage, not semantic or causal ground truth.

## A.4 Split isolation and common support

For each historical descendant-budget view, train and frozen roles are checked for
zero overlap on four axes: unordered pair, endpoint, parent, and referenced physical
run. Row-level deduplication alone is insufficient. Any nonzero overlap on a frozen
axis invalidates the affected comparison rather than being repaired after seeing its
performance.

Predictors are compared only after an exact common-support join. For each predictor,
the public report includes:

- eligible-pair count and coverage fraction;
- ties, parse failures, missing predictions, and excluded reasons;
- pair-micro and task-macro estimates;
- parent- and run-aggregated sensitivity views;
- task-clustered uncertainty, plus declared run/parent sensitivity analyses; and
- leave-one-task-out and dominant-task deletion checks.

A denominator may not be silently changed to favor one model. Coverage and quality
remain separate axes; absence of a prediction is not counted as a correct tie or
removed without disclosure.

## A.5 Decision-time feature and cost contract

The benchmark labels every feature by availability. Source code and declared static
structure can be execution-free. Runtime, stdout, validation curves, execution status,
and self-reported scores are post-execution. Retrospective sibling counts or retained
children are not automatically available to an online selector.

Cost reporting separates:

1. one-time initialization or fitting;
2. online per-candidate or per-pair query latency;
3. memory and hardware used by the predictor; and
4. candidate execution plus external pristine grading.

The historical CPU attestation shows that lightweight online queries are thousands of
times cheaper than median candidate execution. This is a cost opportunity, not evidence
that a selector improves final score or wall-clock time. Search utility requires a
separate equal-budget deployment experiment.

## A.6 Outcome-blind temporal confirmation

The prospective population is the first 960 eligible physical runs in the frozen
chronological registry, followed by an independent accrual-closure receipt. A pair
count is a support condition, not an alternate early stopping rule. Boundary-archive
overshoot follows the preregistered rule and may not be trimmed after outcomes exist.

The maintenance state machine is:

```text
new archive
  -> credential-shape and archive-hash gate
  -> structural eligibility and duplicate gate
  -> append-only snapshot promotion
  -> fixed-scorer prediction receipt / escrow
  -> first-960 identity anchor + independent closure
  -> one-time aggregate join and report
```

Before the last transition, monitoring may read only process ownership, locks, marker
files, hashes, structural counts, and value-free receipts. It may not read labels,
outcomes, prediction values, accuracy, utility, candidate identity, or a private
selection profile. A new stable snapshot must preserve the prior prefix exactly;
unknown duplication, hash drift, or monitor-owner ambiguity fails closed.

At the current value-free snapshot, 296 source archives yield 559 eligible runs,
14,383 endpoints, 3,447 structural pairs, and 45 tasks. The first-960 cohort is not
closed. The latest independently verified fixed-scorer prefix remains the separate
517-run receipt and must not be conflated with the broader 559-run structural state.

## A.7 One-time reporting and no-rescue rule

Before any L3 read, the analysis package must bind:

- the exact identity-anchor and closure hashes;
- every frozen scorer/checkpoint and its training provenance;
- the canonical pair universe and orientation rule;
- the estimand panel and task universe;
- clustering units and bootstrap seeds;
- fixed gap buckets, coverage/tie/missingness definitions, and LOTO views; and
- the output schema, including failed gates and suppressed claims.

The one-time analysis either emits the full preregistered table or a failure receipt.
It may not select a different legal-looking snapshot, change task weights, add seeds,
drop a task, alter a threshold, or substitute a secondary estimand to rescue a failed
primary. Target-522 Stage-A/rank is already classified `LIMITED_SUPPORT`; it cannot be
reopened as a positive or negative result by changing its frozen requirements.

## A.8 Clean capacity-scaling condition

The historical 0.6B-to-8B signal is exploratory because its pair data mix generator/
config strata and some outer-test evaluations were reused during development. A clean
capacity result enters the paper only if a real producer writes canonical config-v2
metadata before outcomes and the following matrix is separately approved:

```text
Qwen3 Base {0.6B, 4B, 8B} x seeds {6, 7}
```

Generator/config stratum, context, optimizer, training steps, prompt, checkpoint rule,
scorer, and budget must be identical except for model size. Checkpoints are selected
on train-run development only; the untouched frozen cohort is evaluated once. The
agent base model is never fine-tuned or RL-updated. Historical model-ID recovery cannot
substitute for outcome-before config-v2 provenance in newly produced runs.

The frozen v2 machine contract requires the pre-test lock to contain 100% canonical
config-v2 sidecar coverage, the sidecar-manifest digest, a stable public generator
release, the exact generator/config stratum, an outcome-before attestation, and an
explicit statement that historical backfill was not used. Both the producer and an
implementation-independent verifier reject a missing or altered field before computing
any performance result.

The capacity claim passes only if the three two-seed task-macro means are nondecreasing,
the mean 8B-minus-0.6B difference is at least 0.02, each seed-specific endpoint
difference is positive, the task-bootstrap lower bound is positive, every high-low
leave-one-task-out difference is positive, and the high-low difference remains positive
after removing the dominant task. Dominance is fixed without outcome values as maximum
primary-pair count, with lexicographically smallest task ID breaking ties. Baseline and
component-gain claims are separately gated and cannot rescue a failed capacity primary.

## A.9 Statistical dependence and label repeatability

Sibling pairs share parents, runs, and tasks. Pair-i.i.d. binomial intervals are not
the primary uncertainty calculation. Task-clustered inference is primary because task
generalization is the intended benchmark claim; run- and parent-aggregated views expose
within-task dependence and large sibling sets. Every table reports the number of tasks,
runs, parents, pairs, and the dominant task/run share.

Independent regrading measures observed ordering agreement. A transported single-label
quantity is reported only with the exchangeability and symmetric-error assumptions that
identify it. Buckets with insufficient repeated labels remain unestimable rather than
being pooled after results are seen.

## A.10 Release governance and redaction

Scientific reproducibility and public-release permission are separate gates.

- The v11 schema inventory is complete, but schema completeness is not content safety.
- The frozen content scan covers prepared text for 23 of 25 tasks. A conservative rule
  frozen before task/card disposition sends 15,174 cards to later content review and
  838 to structure-only release; “content-review eligible” does not mean clean.
- Exact archived configuration recovery supplies a configured model ID for all 16,012
  rows and an exact version-or-model identifier for 15,905. Provider-family provenance
  still covers only 9,901 rows; 6,111 remain unresolved for service provider/account/
  contract, so model ID completeness is not terms or license clearance.
- Raw archives are scanned for credential shape before human reading. A hit requires
  remote streaming redaction; secrets are never copied locally or committed.
- Competition data are not redistributed. Final publication still requires per-task
  rule review, provider-output terms, credential/PII/path review, LICENSE/NOTICE,
  `licenses.json`, and truthful Croissant/RAI publication fields.

## A.11 Formal-run and failure-record contract

Each formal run uses a fresh exact-commit worktree and a new immutable result root. It
records protocol/input hashes, environment and dependency versions, all random seeds,
the exact command/config, focused and full tests, producer A/B, a non-importing verifier
A/B, file/network traces, permission modes, and a postflight manifest. Outputs are made
read-only after completion.

Failure is evidence. A failed attempt keeps its root and machine-readable reason; it is
not overwritten or omitted from the paper trail. Engineering repairs may change only
the demonstrated harness defect and must use a new commit/root. Scientific thresholds,
population, estimand, and reporting rule remain frozen. Commit titles containing counts
are copied from machine output rather than recomputed manually.

## A.12 Evidence routing for this appendix

| Appendix claim | Authoritative entry point |
|---|---|
| v11 hierarchy, rows, strict core, split isolation | `results/decision_corpus_audit_v11_20260814/`; Evidence Index v10 `decision_corpus` |
| source opportunity and observability | Evidence Index v10 `source_opportunity`, `decision_observability` |
| status partial order and answerability | Evidence Index v10 `status_certified_partial_order`, `source_decision_answerability` |
| label repeatability | `results/label_repeatability_v2_20260814_4e3bebe/` |
| deployment cost | `results/deployment_cost_attestation_v2_20260820_c800345/` |
| pair weighting | Evidence Index v10 `structural_weighting_shift`, `opportunity_yield_aggregation_audit` |
| prospective structure and fixed-scorer prefix | `prospective_structural_status_receipt_20260902.json`; Evidence Index v10 `prospective_wl_snapshot_chain_517` |
| release content tier | `release_content_scan_postflight_receipt_20260902.json`; `release_content_tier_postflight_receipt_20260902.json` |
| generator provenance axes | `archived_generator_provenance_postflight_receipt_20260902.json`; `generator_provenance_completion_postflight_receipt_20260902.json` |
| claim withdrawals | `PAPER_APPENDIX_CLAIM_WITHDRAWALS_20260902.md` |
| benchmark reporting checklist | `results/agentic_benchmark_checklist_crosswalk_v2_20260826_c97371d/` |

Before submission, internal paths in this table must be replaced by archival artifact
links or appendix labels. No citation may point to a withdrawn result as active support.
