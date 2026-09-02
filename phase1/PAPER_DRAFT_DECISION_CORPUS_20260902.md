# Decision Corpus: Auditing Predictors for ML-Engineering Agent Search Trees

> Internal manuscript draft v0.2, 2026-09-02. This draft is governed by
> `CURRENT_DIRECTION.md` and Evidence Index v10. Bracketed result slots are sealed;
> they must not be filled before the corresponding preregistered gate closes.

## Abstract

ML-engineering agents generate alternative programs whose quality is observed only
after costly execution and training. A cheap pre-execution predictor could allocate
this budget, but evaluating such predictors is not ordinary pairwise classification:
the evaluation population is induced by a partially observed search tree, and its
apparent performance can be confounded by physical-run leakage, incomplete choice
sets, pair-induced reweighting, label noise, and post-execution signals presented as
free baselines. We introduce **Decision Corpus**, a rebuildable benchmark of
provenance-bound sibling decision fragments from real AIRA-dojo searches, together
with a common-support predictor suite and a machine-verifiable audit protocol. The
historical v11 release contains 16,012 cards and 8,107 audited direct-sibling rows;
7,579 rows form a parent-present strict core. Same-budget training and frozen splits
have zero overlap in unordered pairs, endpoints, parents, and referenced physical
runs. On an independently regraded ten-task subset, ordering agreement is 96.6%
micro and 98.0% task-macro. Under a pinned CPU deployment protocol, lightweight
predictor queries are 4,048--6,037 times cheaper than median candidate execution.
We further show that balancing collected runs need not balance decision pairs:
task-specific decision-opportunity yield changes the benchmark estimand and reverses
the temporal direction of run-level and pair-level concentration. A frozen
competition-data screen conservatively routes 15,174 of 16,012 historical cards
(94.766425%) to further legal/privacy content review and 838 to structure-only
release; this is not release clearance. A sealed, append-only chronological cohort
currently contains 559 eligible runs, while its labels and prediction values remain
hidden pending preregistered closure.
**[SEALED: one-shot prospective common-support predictor table.]** Decision Corpus
turns critic evaluation for ML-agent search into a versioned, cost-aware, and
leakage-resistant measurement problem, and releases reconstruction manifests,
independent verifiers, and a claim-withdrawal ledger alongside the data.

## 1. Introduction

An ML-engineering agent repeatedly proposes code, executes it, observes failures or
validation performance, and decides what to try next. This loop creates a basic
resource-allocation problem: among several unexecuted candidates, which one is most
likely to justify its execution cost? A predictor that can answer this question from
code and decision-time context could accelerate search without modifying the agent
model itself.

The tempting evaluation is to collect programs, form labeled pairs, and report the
fraction for which a predictor selects the higher-scoring program. That evaluation
is fragile. Programs adjacent in a serialized trajectory may come from different
choices. A parent may have been pruned from the public artifact. Training and test
pairs may be disjoint while still sharing a physical search run. A task that produces
many retained children contributes quadratically more pairs than a task with the same
number of runs but fewer opportunities. A self-reported score is available only
after the candidate has executed and therefore is not a free pre-execution baseline.
Finally, repeated grades and failed executions induce uncertainty and partial orders
that cannot safely be collapsed into a single noiseless total order.

These are not cosmetic reporting choices. They determine the estimand: the
population over which “predictor accuracy” is averaged. A benchmark can therefore
look balanced at the run level while being dominated by a different task at the pair
level, or can appear to generalize while reusing latent run context across its split.
The central premise of this work is that a useful predictor benchmark for
ML-engineering search must make this induced population explicit.

We present Decision Corpus, a dataset and audit protocol built around that premise.
Its released unit is a provenance-bound recorded-parent sibling fragment, not a
generic trajectory transition or a claimed-complete choice set. Historical
development data are separated on four observable leakage axes. A chronological
confirmation cohort is accumulated outcome-blind: identities are fixed by an
append-only registry, predictions are escrowed, and outcomes remain sealed until a
one-time closure rule is satisfied. Predictor quality, coverage, calibration, and
initialization/query cost are evaluated on exact common support.

Our contributions are:

1. **A decision-level corpus for ML-engineering search.** We release versioned cards,
   sibling fragments, run/parent/endpoint provenance, deterministic rebuild
   manifests, and explicit strict-core versus recoverable-fragment tiers.
2. **A cost-aware predictor benchmark.** Static, text, embedding, reward-model, and
   judge families are compared on common support with initialization, online query,
   and candidate-execution costs kept separate.
3. **An executable audit protocol.** Physical-run isolation, choice observability,
   label repeatability, source missingness, duplicate scope, pair weighting,
   outcome-blind closure, independent reconstruction, and claim withdrawal are
   represented by machine-verifiable receipts rather than prose alone.
4. **An empirical measurement finding.** In the observed search distribution,
   task-specific decision-opportunity yield makes run-balanced accrual diverge from
   pair-balanced evaluation. Pair-micro accuracy is consequently a property of the
   pairing process as well as of the predictor.

We do not claim the first or largest MLE trajectory dataset, the first reward model
trained from search trees, complete choice sets, or an end-to-end search improvement
before the sealed confirmation protocol permits that conclusion.

## 2. Related Work

### MLE trajectories and actor learning

ML-Agent, OpenMLE/Frontis-MA1, and mle-traj establish that execution-grounded MLE
traces can support behavior analysis, supervised actor training, and learned search
operators. These resources close novelty claims based only on releasing scored
program trajectories or tree-shaped histories. Decision Corpus instead treats the
choice among unexecuted siblings as the evaluation unit and focuses on measurement:
which candidate information is available at decision time, which physical units are
shared across splits, and how the search process weights the resulting benchmark.

### Value and reward models for search

AgentRM, step-level Q-value models, ReLoc, and related code-search systems already
establish value learning from process states, parent-local revisions, or search
trees. Our contribution is not the existence of a tree-derived critic. We provide a
dataset-first comparison of predictor families under a fixed sibling estimand,
explicit query/execution cost accounting, and a sealed temporal confirmation
protocol. The agent foundation model is not fine-tuned or updated by this project.

### Performance-predictor benchmarks

Neural architecture search offers the closest measurement precedent. NAS predictor
studies distinguish predictor initialization cost from query cost and evaluate
multiple predictor families on reusable tabular benchmarks. Decision Corpus adopts
that discipline for generated ML programs, where observations are noisier, failures
create partial orders, code carries task and generator shortcuts, and the candidate
population is itself produced by an adaptive agent search.

### Benchmark governance

BenchmarkCards, BetterBench, ReproEval-style documentation, and agentic benchmark
checklists motivate explicit data statements and reproducibility records. We apply
these principles at artifact level: each claim routes to an evidence entry with an
exact population, hash, verifier, failure gate, and `does_not_prove` boundary.
Retracted or superseded claims remain in an append-only ledger.

## 3. From Search Archives to Decision Corpus

### 3.1 Units and provenance

The corpus follows the hierarchy

```text
archive -> physical run -> endpoint/card -> recorded parent -> sibling fragment.
```

An archive is an immutable uploaded search artifact. A physical run is a single
agent-search execution reconstructed from source journals when available and from a
documented segmentation rule otherwise. An endpoint/card records a candidate program
and its search context. A decision parent is the recorded parent shared by retained
children from the same physical run. Pair rows orient two finite-grade children of
that parent. We use “fragment” deliberately: retained children are fully represented
within the released graph, but children absent from the archive cannot be recovered.

Figure 1 summarizes this unit hierarchy and the sealed evaluation path. It keeps the
historical development track, chronological confirmation track, and conditional clean
scaling track visually distinct, and shows that prediction escrow and outcome vault
may be joined only through the one-time closure anchor.

### 3.2 Labels and relation types

Numeric quality is computed by an external pristine evaluator rather than workspace
code that the agent may modify. Finite continuous grades induce oriented numeric
pairs. Execution status supplies a separate certified-validity partial order, such as
a valid execution dominating an error-only candidate. Unknown numeric relations stay
unknown; status dominance is not imputed as a continuous score difference. Runtime,
stdout, and self-reported scores are classified as post-execution information and
are excluded from execution-free predictor inputs.

### 3.3 Historical releases and split isolation

The v11 card release is reconstructed from 29 immutable LFS batches and contains
16,012 rows across 25 tasks. Its byte length and SHA-256 are fixed by the release
descriptor. Nine decision resources cover train, frozen, and extension roles at
three historical descendant-budget views. Across those resources, 8,107 rows are
verified direct siblings within a reconstructed physical run. The parent-present
strict core contains 7,579 rows; 528 rows are retained as a separately reported
lineage-verifiable orphan-parent tier.

For each budget, train and frozen roles have zero overlap in unordered pairs,
endpoints, parents, and referenced physical runs. This is stronger than row-level
deduplication and prevents a predictor from exploiting run-specific context shared
across the nominal split. It does not establish decontamination from foundation-model
pretraining or secrecy of public competition tasks.

### 3.4 Outcome-blind temporal confirmation

Historical results remain development evidence. A separate chronological cohort is
formed from the first eligible physical runs under a preregistered ordering and an
outcome-independent accrual-closure receipt. Intake is append-only and validates
archive hashes, source/run/endpoint identity, and cross-batch duplication before
promotion. Fixed models write prediction escrow without opening the label vault.
The one-time evaluation may occur only after the identity cohort and closure receipt
are fixed. At the current structural snapshot, 296 source archives yield 559 eligible
runs, 14,383 endpoints, and 3,447 structural pairs across 45 tasks. The cohort is 401
runs short of its first-960 target and has no closure receipt. These are structural
statements only, not interim performance estimates; no outcome, label, prediction,
candidate identity, or private profile was opened to produce them.

## 4. Predictor Benchmark

### 4.1 Estimands

No single average is sufficient. We report pair-micro accuracy, task-macro accuracy,
parent- and run-aggregated performance, exact support coverage, tie/missingness rates,
calibration, and leave-one-task-out sensitivity. Pair-micro answers the performance
under the benchmark's realized pair distribution. Task-macro gives each task equal
weight. Parent/run summaries reduce the influence of large sibling sets and repeated
pairs. These estimands are presented together rather than selecting the most
favorable one after observing outcomes.

### 4.2 Predictor families and common support

The suite includes random and simple structural baselines; static code features;
character TF-IDF; frozen code embeddings with a lightweight classifier; independent
reward models; and external LLM judges where cost permits. Each row records whether
features are available before execution. Predictors are joined to the exact same
eligible pair pool before paired comparison. Coverage differences are reported and
are never silently converted into favorable denominators.

Historical model development uses train-run development only. A checkpoint cannot be
selected through repeated evaluation on the frozen temporal cohort. Any future
capacity-scaling result must hold generator/config stratum, context, optimizer,
steps, prompt, checkpoint rule, and budget fixed while changing only model size.

### 4.3 Cost accounting

We separate one-time initialization from online query latency and compare both with
candidate execution. Candidate execution includes the program and model-training work
needed to obtain the external score. Under a pinned CPU protocol, static LR, GBM, and
TF-IDF online pair queries have median latency 4,048--6,037 times below median
candidate execution. This establishes room for budget savings; it does not by itself
show that a predictor improves final search score or end-to-end wall time.

### 4.4 Uncertainty and dependence

Pairs sharing tasks, runs, or parents are dependent. Primary uncertainty is therefore
clustered by task, with run/parent analyses and leave-one-task-out checks reported as
sensitivity views. Pair-i.i.d. binomial intervals are not used as the main evidence.
Repeated-label analyses distinguish observed agreement from transported ceilings and
state the exchangeability and symmetric-error assumptions required by the latter.

## 5. Audit Findings

### 5.1 Decision rows are not automatically independent search choices

The audit found that direct-sibling lineage must be reconstructed and checked rather
than inferred from serialized adjacency. The strict-core/recoverable-tier split makes
parent absence visible. Same-budget train/frozen overlap is zero on four explicit
axes, but one of 36 support gates fails because a frozen descendant-budget resource
has excessive single-run pair concentration. We therefore do not summarize the
release as having passed every integrity gate.

### 5.2 Label noise does not explain away the measured signal

Independent regrading covers 207 usable cards from ten tasks and yields 3,017
original-versus-repeat pair observations. Raw ordering agreement is 0.965860 and
task-macro agreement is 0.980181. This indicates substantial repeatability on the
measured subset. It is not a universal ceiling: task transport and inferred
single-label quantities require additional assumptions.

### 5.3 Pair construction changes task weights

Let each task contribute runs at rate \(r_t\) and usable sibling opportunities at
yield \(y_t\). Pair weight is proportional not merely to \(r_t\), but to the number
and size of retained sibling sets induced by \(y_t\). In the observed temporal
accrual, run-level task concentration decreases while pair-level concentration
increases. The total-variation distance between run and pair task distributions is
0.337083; a decomposition attributes approximately 0.645 of the HHI increment and
0.595 of the TV increment to opportunity-yield heterogeneity. The direction survives
temporal and leave-one-task-out checks, although the magnitude is sensitive to one
high-leverage task. The result motivates reporting both physical-unit and pair-level
weights in predictor benchmarks.

Figure 2 visualizes this trajectory from run 120 onward. The discontinuity at run
260 is explicitly annotated as one high-leverage drop rather than smoothed away;
the figure caption therefore separates the task-deletion-robust direction from the
non-robust magnitude. Its PNG/SVG and hash receipt are in
`phase1/figures/decision_corpus_20260902/`.

### 5.4 Duplicate, provenance, and structural-gate scope

Fixed exact, token, and AST normalizations show no observed cross-run or cross-task
duplicate groups within their covered subset. Because AST coverage is not complete
and semantic/pretraining matching is outside the detector, this is a bounded negative
audit rather than a claim of no contamination. Separately, archive-level structural
gates reject 14 events affecting seven competitions in the settled 283-archive state.
Six retain accepted support; the only no-support event links to roots with no
checkpoint data. Thus the current gate is support-preserving on this observed state,
not universally lossless.

## 6. Benchmark Results

### 6.1 Historical development results

Table 4A is a development calibration, not the direct-sibling confirmation. Its
exact-common-support source is the independently verified 931-row historical
preference graph: 28 tasks, 550 decision parents, and no support differences among
the reported rows. The graph has incidence rank 787 and 144 cycle rows. Moreover,
144 of 931 comparisons span two endpoint runs, so these results must not be relabeled
as the within-physical-run estimand used by the current corpus.

**Table 4A(a): historical common-support development calibration.** The frozen
headline averages pair credit within parent, parents within task, and tasks uniformly.
UST columns weight graph edges by their uniform-spanning-tree inclusion probability.
Intervals are task-clustered; support is 931/931 and prediction ties are zero for every
row. The task-conditioned arms are in-task development baselines.

| Predictor | Pair micro | Uniform task→parent→pair | UST task→parent→pair (95% CI) | Support / ties |
|---|---:|---:|---:|---:|
| Random hash | 0.5134 | 0.5169 | 0.5164 [0.4557, 0.5757] | 931 / 0 |
| Static LR, pooled | 0.5005 | 0.4648 | 0.4652 [0.3899, 0.5348] | 931 / 0 |
| Static LR, task-conditioned | 0.5371 | 0.5028 | 0.5023 [0.4349, 0.5668] | 931 / 0 |
| Static GBM, pooled | 0.5532 | 0.5354 | 0.5357 [0.4813, 0.5951] | 931 / 0 |
| Static GBM, task-conditioned (dev-selected) | 0.5607 | 0.5480 | 0.5483 [0.4982, 0.6008] | 931 / 0 |
| Character TF-IDF + LR | 0.5714 | 0.5665 | 0.5666 [0.4984, 0.6310] | 931 / 0 |

The dev-selected static GBM has a paired UST headline difference of -0.0183 versus
TF-IDF (95% CI [-0.1091, 0.0863]). UST weighting changes its own headline by only
+0.0003 (95% CI [-0.0004, 0.0011]), and the primary-model ordering has no discordance
between uniform and UST weighting. Thus the graph correction is structurally
non-trivial but does not create a predictor-performance breakthrough.

**Table 4A(b): separately measured deployment cost.** These are model-family paths
on the pinned v11 b0 CPU protocol, not timings inferred from Table 4A(a), and the
cost run did not compute accuracy. Ranges are the two independent runs.

| Measured path | Initialization p50 (s) | Pair query p50 (ms) | Execution p50 / query p50 |
|---|---:|---:|---:|
| Static LR | 153.09--153.54 | 40.91--41.00 | 4,868--4,880× |
| Static GBM | 154.79--155.04 | 49.04--49.31 | 4,048--4,071× |
| Character TF-IDF + LR | 98.59--107.47 | 33.07--33.93 | 5,884--6,037× |

Embedding, reward-model, and LLM-judge rows do not have an independently verified
931-row common-support artifact and are therefore not silently imported from the old
400-pair report. Their full-family comparison remains in the sealed chronological
Table 4B. Table 4A does not claim prospective generalization, task-unseen transfer, or
search utility.

### 6.2 Sealed chronological confirmation

**[SEALED TABLE 4B.]** This subsection will be populated once the preregistered
identity cohort and accrual-closure receipt permit a one-shot join of escrowed
predictions and labels. Until then, no accuracy, calibration, utility, candidate
identity, or private selection profile is inspected or reported.

### 6.3 Conditional clean capacity scaling

**[CONDITIONAL TABLE 5.]** Model-size scaling enters the paper only if a real producer
writes outcome-before config-v2 provenance and an approved 0.6B/4B/8B by two-seed
matrix changes no other training or evaluation factor. Otherwise the existing signal
is identified as exploratory and remains outside the main evidence.

## 7. Limitations, Governance, and Release

Decision Corpus contains observed sibling fragments, not the complete counterfactual
set of candidates the agent might have generated. Some historical physical runs rely
on deterministic segmentation because source journals are incomplete. Tasks are
drawn from public competition-style ML problems and may be represented in foundation
model pretraining. Generator, operator, hardware, time, task difficulty, execution
failure, and retention all influence the observed population.

The v11 schema is machine-inventoried, but data release is not yet legally or
content-cleared. The frozen content scan covers prepared data for 23 of 25 tasks and
tests 3,766,518 fixed high-entropy patterns. It finds 173 matched patterns affecting
419 cards, while the two unscanned tasks contain another 419 cards. A rule frozen
before task/card disposition therefore routes 15,174 cards to later content review
and 838 to structure-only release, withholding both code and stdout for every
matched or unscanned card. Producer A/B, an independently implemented verifier, and
an independent postflight reconstruction are byte-exact. “Content-review eligible”
is deliberately not called clean or cleared: raw-match adjudication, the two missing
prepared sources, credential/PII/path checks, and legal review remain. All 25
official competition rules pages have been triaged, but seven compact legacy pages
and two nonstandard detailed templates still require institutional interpretation.
A metadata-only inventory plus exact archived `dojo_config` reconstruction recovers
the configured generator model ID for all 16,012 rows and an exact version-or-model
identifier for 15,905 (99.33%). This does not identify the serving provider or
contract: provider-family provenance remains available for only 24 of 29 immutable
batches (9,901 rows), leaving five batches (6,111 rows) unresolved on that separate
axis, while two Qwen-annotated batches also lack a collection-time contracting entity
and terms record. Provider-output terms, final licenses/notices, and privacy/path
scanning therefore remain release gates. Croissant 1.1 and Responsible AI 1.0 generation is now backed
by a value-free, independently checked builder over all 10 release resources, but
the final JSON-LD is deliberately absent until the real license, landing page,
creator, publication date, and content base URL are fixed and every independent
release gate closes. Immutable historical batches are
never silently edited. If sanitation
is required, a new append-only successor and receipt are created while the affected
version remains documented.

Scientific claims are governed by an Evidence Index. Each entry fixes its population,
estimand, artifact hashes, verifier, and non-implications. Reconstruction or derived
certificates do not count again as independent evidence. Failures and withdrawals are
preserved, including earlier conclusions invalidated by run leakage, common-support
mismatch, or post-execution baseline framing. Appendix A classifies each material
correction as a retracted result, scope correction, hypothesis kill, provenance
withdrawal, novelty withdrawal, or evidence-dedup correction, and states the exact
rule preventing the superseded claim from silently returning.

## 8. Conclusion

A useful critic for ML-engineering search must be cheaper than execution, but a
credible benchmark must also say which choices, runs, tasks, and information states
its score represents. Decision Corpus provides provenance-bound sibling fragments,
a cost-aware common-support predictor suite, and an executable audit trail for that
measurement problem. Its historical release shows that run isolation, label
repeatability, and pair-weight accounting materially change the interpretation of
predictor results. Its sealed temporal cohort is designed to test whether those
results transport without repeated access to outcomes. The resulting resource is a
benchmark for predictors and, equally, a benchmark for the claims made about them.

## Internal evidence routing (remove before submission)

- Corpus/split numbers: Evidence Index v10 `decision_corpus`.
- Label agreement: `label_repeatability`.
- Cost ratios: `deployment_cost`.
- Pair-weight shift: `structural_weighting_shift`.
- Prospective structural counts: `prospective_structural_status_receipt_20260902.json`;
  outcome/label/prediction/identity/profile remain sealed.
- Structural gate scope: `archive_rejection_support_census` and the derived utility
  certificate; do not count the latter as distinct evidence.
- Table 1--3 copy-ready material: `PAPER_TABLES_1_3_DRAFT_20260902.md`.
- Schema/release boundaries: `SCHEMA_DICTIONARY_DECISION_CORPUS_V11_20260902.md` and
  `DATACARD_DECISION_CORPUS_DRAFT_20260902.md`.
- Machine-readable metadata readiness: `CROISSANT_RAI_READINESS_V11_20260902.md`;
  this is release engineering, not scientific-claim evidence or clearance.
- Rules triage: `KAGGLE_RULES_TRIAGE_V11_20260902.md` and
  `licenses_v11_draft.json`; this is not legal clearance.
- Content scan/tiering: `release_content_scan_postflight_receipt_20260902.json` and
  `release_content_tier_postflight_receipt_20260902.json`; these are release
  engineering evidence, not predictor-effect evidence or release clearance.
- Generator provenance: `archived_generator_provenance_postflight_receipt_20260902.json`
  and `generator_provenance_completion_postflight_receipt_20260902.json`; configured
  model IDs are complete, but provider/contract provenance and release clearance are not.
- Claim-withdrawal appendix: `PAPER_APPENDIX_CLAIM_WITHDRAWALS_20260902.md`.
- Reproducibility/audit appendix: `PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260902.md`;
  prospective result slots remain sealed and no path in this appendix authorizes an L3 read.
