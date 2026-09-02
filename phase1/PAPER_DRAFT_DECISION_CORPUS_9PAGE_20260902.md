---
title: "Decision Corpus: Auditing Predictors for ML-Engineering Agent Search Trees"
author:
  - "Anonymous Author(s)"
reference-section-title: "References"
abstract: |
  ML-engineering agents generate alternative programs whose quality is observed only
  after costly execution. A cheap pre-execution predictor could allocate this budget,
  but its evaluation population is induced by a partially observed search tree and can
  be confounded by physical-run leakage, incomplete choice sets, pair-induced task
  weighting, label noise, and post-execution signals presented as free baselines. We
  introduce Decision Corpus, a rebuildable benchmark of provenance-bound sibling
  fragments from real AIRA-dojo searches, with a common-support predictor suite and a
  machine-verifiable audit protocol. The historical build contains 16,012 cards and
  8,107 audited direct-sibling rows, including a 7,579-row parent-present strict core.
  Same-budget training and frozen splits have zero overlap in unordered pairs,
  endpoints, parents, and referenced physical runs. Independent regrading yields 96.6%
  micro and 98.0% task-macro ordering agreement on a ten-task subset, while lightweight
  predictor queries are 4,048-6,037 times cheaper than median candidate execution under
  a pinned CPU protocol. We show that structural pair share is exactly run share
  size-biased by task-specific decision-opportunity yield; in the observed chronology,
  run-level concentration falls while pair-level concentration rises. A separate
  append-only cohort contains 559 eligible runs whose outcomes and predictions remain
  sealed pending preregistered closure. The result is a versioned, cost-aware, and
  leakage-resistant measurement framework for predictors over agent search trees.
---

# Introduction

An ML-engineering agent repeatedly proposes code, executes it, observes failures or
validation performance, and decides what to try next. This loop creates a basic
resource-allocation problem: among several unexecuted candidates, which one is most
likely to justify its execution cost? A predictor that answers this question from code
and decision-time context could accelerate search without modifying the agent model.

The obvious evaluation - collect programs, form labeled pairs, and report how often a
predictor selects the higher-scoring program - is fragile. Adjacent serialized records
may not be alternatives from one choice. A parent may be absent from a pruned artifact.
Pair-disjoint splits may still share a physical search run. Tasks with larger retained
sibling sets create many more pairs than tasks with the same number of runs. A
self-reported score is observed only after execution and is therefore not a free
pre-execution baseline. Repeated grades and failed executions further create uncertainty
and partial orders that a noiseless binary label obscures.

These decisions define the estimand: the population over which predictor accuracy is
averaged. A benchmark can look run-balanced while its pair distribution is dominated by
a different task, or appear to generalize while reusing latent run context across its
split. We therefore treat predictor evaluation as a provenance and measurement problem,
not ordinary pairwise classification.

Decision Corpus uses a provenance-bound recorded-parent sibling fragment as its unit.
Historical development data are isolated on observable pair, endpoint, parent, and
physical-run axes. A chronological confirmation cohort is accumulated outcome-blind:
identities are fixed by an append-only registry, predictions are escrowed, and outcomes
remain sealed until an independently checkable closure rule is satisfied. Predictor
quality, coverage, dependence, and initialization/query cost are evaluated on exact
common support.

Our contributions are:

1. **A decision-level corpus.** Versioned cards and sibling fragments carry explicit
   archive, physical-run, parent, endpoint, source, and reconstruction provenance, with
   strict-core and recoverable-fragment tiers rather than a false complete-choice claim.
2. **A cost-aware predictor benchmark.** Structural, static-code, text, embedding,
   reward-model, and judge families share a common-pool contract that separates one-time
   initialization, online query, and candidate-execution cost.
3. **An executable audit protocol.** Split isolation, parent observability, label
   repeatability, source missingness, duplicate scope, pair dependence, outcome-blind
   closure, and claim withdrawals are bound to versioned receipts and independent
   verifiers.
4. **An empirical estimand finding.** Task-specific decision-opportunity yield makes
   run-balanced accrual diverge from pair-balanced evaluation. We give the exact
   size-bias identity, its total-variation leverage bound, and the zero-support case in
   which a full-task predictor estimand is not identifiable.

We do not claim the first MLE trajectory dataset, the first tree-derived reward model,
the first pre-execution MLE preference mechanism, complete source choice sets, or an
end-to-end search improvement before the sealed protocol permits that conclusion.

# Related work

FOREAGENT releases curated within-task solution comparisons and a Predict-then-Verify
agent [@zheng2026foreagent]. AI Research Preference Models (RPMs) intervene closer to
our setting: AIRA-dojo generates 15 unexecuted children and an inference-only judge or
pilot selects one for execution, with positive end-to-end evidence on 20 tasks
[@foster2026rpm]. RPM's separate offline set uses observed-subtree maxima and explicitly
discusses off-policy and subtree-opportunity bias. These works establish the value of
pre-execution preference; our different question is how naturally logged sibling
fragments should be measured under physical-run identity, incomplete choices,
failure/unknown relations, pair weighting, cost, and one-shot temporal transport. RPM is
therefore a required method reference and a transfer baseline after closure, not a
result superseded by this corpus.

ML-Agent, OpenMLE/Frontis-MA1, and mle-traj establish execution-grounded traces for
actor training and behavior analysis [@liu2025mlagent; @yang2026frontisma1;
@jerryyan2026mletrajv1; @jerryyan2026mletrajv3]. AgentRM, step-level Q models, and
ReLoc already learn value or reward signals from process states, search trees, or
parent-local code revisions [@xia2025agentrm; @zhai2024stepq; @lyu2025reloc]. Our
contribution is consequently not the existence of a tree critic, but a dataset-first
cross-family measurement contract.

NAS predictor benchmarks provide the closest methodological precedent: they compare
families on reusable tabular spaces and distinguish initialization from query cost
[@white2021predictors; @krishnakumar2022nasbenchsuitezero; @tu2022nasbench360].
Informative cluster size similarly shows that unit- and cluster-weighted summaries
target different estimands [@williamson2003informativeclusters;
@kahan2023clusterestimands]. We apply these ideas to decisions produced by adaptive
MLE-agent search. Recent DeltaML-Bench and BAITBENCH already cover real-repository MLE
evaluation and specification-gaming or hidden-split integrity audits
[@moukpe2026deltamlbench; @prasad2026baitbench]. The scoped distinction here is the
combination of logged sibling fragments, cross-family predictors, and an explicit
physical-unit/pair estimand map, not generic benchmark integrity.

# From search archives to Decision Corpus

## Units, labels, and provenance

The corpus hierarchy is archive $ightarrow$ physical run $ightarrow$ endpoint/card
$ightarrow$ recorded parent $ightarrow$ sibling fragment. An archive is an immutable
uploaded search artifact. A physical run is one agent-search execution reconstructed
from source journals when available and by a documented segmentation rule otherwise.
An endpoint records a candidate program and search context. Pair rows orient two
finite-grade children that share a recorded parent, task, and physical run. We call the
unit a fragment because retained children are represented, but children absent from the
archive cannot be recovered.

Numeric quality comes from an external pristine evaluator rather than code in the
agent's mutable workspace. Finite grades induce oriented numeric pairs. Execution
status supplies a separate validity partial order, such as a valid execution dominating
an error-only candidate. Unknown numeric relations remain unknown; status dominance is
not imputed as a continuous score difference. Runtime, stdout, and self-reported scores
are post-execution information and are excluded from execution-free predictor inputs.

![Corpus units and sealed evaluation protocol. Historical development, outcome-blind
chronological confirmation, and conditional clean scaling remain separate. Prediction
escrow and the outcome vault can be joined only after the closure anchor. The diagram
reports protocol structure, not performance, identity, utility, or a completed scaling
result.](figures/decision_corpus_20260902/figure1_corpus_and_sealed_protocol.png){width=92%}

## Historical and chronological populations

The v11 card build is reconstructed from 29 immutable batches and contains 16,012 rows
across 25 tasks. Nine decision resources contain 8,107 verified direct-sibling rows;
7,579 have the recorded parent present, and 528 form a separately reported
lineage-verifiable orphan-parent tier. Within each descendant-budget view, training and
frozen roles have zero overlap in unordered pairs, endpoints, parents, and referenced
physical runs. This is stronger than row deduplication but does not establish
foundation-model pretraining decontamination or secrecy of public tasks.

| Population | Units | Runs/tasks | Interpretation |
|---|---:|---:|---|
| Historical card build | 16,012 cards | 667 segments / 25 | 14,339 cards have source-truth provenance |
| Historical decision rows | 8,107 pairs | multiple roles | 7,579 strict-core; 528 orphan-parent tier |
| b0 train / frozen | 4,263 / 1,498 pairs | 333 / 92 runs | development roles; four-axis overlap is zero |
| Chronological intake | 3,447 structural pairs | 559 runs / 45 tasks | 14,383 endpoints; outcomes remain sealed |
| Producer config-v2 | 0 sidecars | - | exact-stratum clean scaling remains blocked |

Historical results remain development evidence. The chronological cohort consists of
the first eligible physical runs under a preregistered order and a separate
outcome-independent accrual-closure receipt. Intake validates archive hashes,
source/run/endpoint identity, and cross-batch duplication before append-only promotion.
Fixed models write prediction escrow without opening labels. At the 2026-09-02
structural snapshot, 296 archives yield 559 eligible runs, 14,383 endpoints, and 3,447
structural pairs over 45 tasks. The cohort remains 401 runs short of first-960 and has
no closure receipt. These are support counts only; no outcome, prediction, accuracy,
candidate identity, or private selection profile was opened to obtain them.

# Predictor benchmark and audit estimands

## Common support, cost, and dependence

We report pair-micro, task-macro, parent- and run-aggregated performance, support,
ties/missingness, calibration, and leave-one-task-out sensitivity. Pair-micro targets
the realized pair distribution; task-macro weights tasks uniformly; parent/run views
limit the influence of large sibling sets and repeated comparisons. The views are
frozen together rather than selected after observing outcomes.

Predictor families include random and structural baselines, static code features,
character TF-IDF, frozen code embeddings with a lightweight classifier, independent
reward models, and external judges where cost permits. Each feature is classified by
decision-time availability. Comparisons use the exact intersection of eligible pair
IDs, and coverage differences remain explicit. Model development uses training-run
dev only; the temporal cohort cannot be queried repeatedly for checkpoint selection.

Initialization and online query are measured separately from candidate execution,
which includes program execution and model training needed to obtain the external
score. This distinction makes a critic's resource motivation testable without treating
a post-execution self-report as free. Pairs sharing a task, run, or parent are dependent,
so task-clustered intervals are primary, with run/parent aggregation and task deletion
as sensitivities. Pair-i.i.d. binomial intervals are not headline evidence.

## Redundant comparison graphs

Rows under one parent form a comparison graph $G=(V,E)$ with predictor credit
$z_e\in[0,1]$. A row mean gives a cyclic graph more mass than a tree over the same
endpoints. We therefore report a graph-basis sensitivity using
$\pi_e=b_e^\top L^+b_e$, the uniform-spanning-tree inclusion probability of edge $e$.
For each connected component,

\[
A_{\mathrm{UST}}(G)=\frac{1}{|V|-1}\sum_{e\in E}\pi_e z_e.
\]

Disconnected components normalize by total incidence rank $|V|-C$ before the frozen
parent-then-task aggregation. This limits raw cycle-count leverage but is not an
independence correction, effective sample size, causal adjustment, or new graph
theorem. Row and UST estimands are therefore shown together.

## Decision-opportunity yield

Let $R_t$ be eligible physical runs, $S_t$ structural exact-common-support sibling
pairs before truth filtering, and $I_t$ informative pairs retained by the frozen rule.
Define run, structural-pair, and informative-pair task mixtures $p_t$, $q_t$, and $r_t$,
with opportunity yield $Y_t=S_t/R_t$ and evaluability $E_t=I_t/S_t$. Then

\[
q_t=\frac{p_tY_t}{\sum_s p_sY_s},\qquad
r_t=\frac{q_tE_t}{\sum_s q_sE_s}.
\]

Thus pair-micro evaluation size-biases the run mixture by opportunity yield and then
by evaluability. For task metric $a_t$,
$A_{\mathrm{struct}}-A_{\mathrm{run}}=\operatorname{Cov}_{p}(Y_t,a_t)/
\mathbb{E}_{p}[Y_t]$, whose magnitude is bounded by the task-metric range times
$\operatorname{TV}(q,p)$. This identity is an estimand map and worst-case leverage
bound, not an observed predictor bias or causal effect. If any cohort task has
$S_t=0$ or $I_t=0$, a full-task impact headline is declared not identifiable rather
than silently dropping the task.

# Audit findings

Direct-sibling lineage cannot be inferred from serialized adjacency. The explicit
strict-core/recoverable split exposes missing parents, and same-budget train/frozen
overlap is zero on four axes. The audit is not uniformly perfect: 35 of 36 support
gates pass, while one frozen descendant-budget resource has excessive single-run pair
concentration. We therefore do not claim that every historical slice is an independent
choice sample.

Independent regrading covers 207 usable cards from ten tasks and 3,017
original-versus-repeat pair observations. Ordering agreement is 0.965860 micro and
0.980181 task-macro. This is substantial repeatability on the measured subset, not a
universal ceiling; transport beyond those tasks requires exchangeability and error
assumptions.

The opportunity-yield effect is visible before opening predictor outcomes. From the
first 240 to 339 eligible runs, run-level task HHI decreases from 0.055972 to 0.048877,
whereas pair-level HHI increases from 0.083038 to 0.135747. The run-to-pair task
total-variation distance is 0.337083. Opportunity-yield heterogeneity accounts for
about 0.645 of the HHI increment and 0.595 of the TV increment. The direction survives
temporal and task-deletion checks, but its magnitude is sensitive to a high-leverage
task and must not be generalized as stable.

![Run-level balance need not imply pair-level balance. The run distribution becomes
less concentrated while the induced sibling-pair distribution becomes more
concentrated. The discontinuity at run 260 is retained as a leverage warning. The
direction survives temporal and task-deletion checks; the magnitude does not. This is
an outcome-blind structural weighting diagnostic, not predictor accuracy, search
utility, or a causal claim about producer behavior.](figures/decision_corpus_20260902/figure2_run_to_pair_weighting.png){width=92%}

Fixed exact, token, and AST normalizations show no observed cross-run or cross-task
duplicate groups in their covered subset. Incomplete AST coverage and untested semantic
or pretraining similarity make this a bounded negative audit, not proof of no
contamination. Separately, archive structural gates reject 14 events over seven
competitions in a settled 283-archive state. Six competitions retain accepted support;
the sole no-support event consists of roots without checkpoint data. The gate is thus
support-preserving on that observed state, not universally lossless.

# Benchmark results

Historical Table 1 is a development calibration, not the sealed direct-sibling
confirmation. Its independently verified exact-common-support graph has 931 rows, 28
tasks, 550 parents, incidence rank 787, and 144 cycle rows. All reported predictors
cover 931/931 rows with zero prediction ties. Moreover, 144 comparisons span two
endpoint runs; these rows cannot be relabeled as the current within-physical-run
estimand. The headline averages credit within parent, parents within task, and tasks
uniformly; intervals cluster by task.

| Predictor | Pair micro | Task-parent mean | UST mean (95% CI) |
|---|---:|---:|---:|
| Random hash | 0.5134 | 0.5169 | 0.5164 [0.4557, 0.5757] |
| Static LR, pooled | 0.5005 | 0.4648 | 0.4652 [0.3899, 0.5348] |
| Static LR, task-conditioned | 0.5371 | 0.5028 | 0.5023 [0.4349, 0.5668] |
| Static GBM, pooled | 0.5532 | 0.5354 | 0.5357 [0.4813, 0.5951] |
| Static GBM, task-conditioned | 0.5607 | 0.5480 | 0.5483 [0.4982, 0.6008] |
| Character TF-IDF + LR | 0.5714 | 0.5665 | 0.5666 [0.4984, 0.6310] |

The dev-selected static GBM differs from TF-IDF by -0.0183 under the paired UST
headline (95% CI [-0.1091, 0.0863]). UST weighting changes the GBM headline by only
+0.0003 (95% CI [-0.0004, 0.0011]), and primary-model ordering has no discordance
between uniform and UST weighting. Redundant-edge weighting is measurable, but it does
not manufacture a model-performance breakthrough.

Separately measured CPU costs show large query headroom:

| Measured path | Init p50 (s) | Pair query p50 (ms) | Execution/query |
|---|---:|---:|---:|
| Static LR | 153.09-153.54 | 40.91-41.00 | 4,868-4,880x |
| Static GBM | 154.79-155.04 | 49.04-49.31 | 4,048-4,071x |
| Character TF-IDF + LR | 98.59-107.47 | 33.07-33.93 | 5,884-6,037x |

These timings establish potential savings, not final-score, wall-clock, or search-utility
gain. Embedding, reward-model, judge, and RPM-transfer rows await a verified common pool
in the chronological cohort and are not copied from an incompatible 400-pair report.

The chronological result remains sealed. It may be evaluated once only after first-960
identity closure and its accrual receipt, using escrowed predictions and the frozen
common-support contract. If closure is not available at submission time, the protocol
and status are reported without an empty result table. Clean model-size scaling is also
excluded unless real outcome-before config-v2 provenance exists and a separately
approved 0.6B/4B/8B by two-seed matrix changes no other factor.

# Limitations, governance, and release

Decision Corpus contains observed sibling fragments, not all candidates the agent
could have generated. Some physical runs use deterministic segmentation because source
journals are incomplete. Public competition tasks may appear in foundation-model
pretraining. Generator, operator, hardware, time, execution failure, and retention
shape the observed population, so the benchmark does not identify a universal search
policy or causal effect of a predictor.

Content-bearing data are not yet release-cleared. A rule frozen before inspecting
task/card disposition routes 15,174 of 16,012 cards to further content review and 838
to a structure-only tier. This screen covers prepared data for 23 of 25 tasks; raw
match adjudication, the two missing sources, credential/PII/path checks, provider terms,
licenses/notices, and institutional legal review remain open. Configured generator
model ID is recovered for all 16,012 rows, but provider-family provenance covers only
9,901; no provider or rights are inferred for the remaining rows. A Croissant/RAI
builder exists, but final metadata remain absent until real license, landing-page,
creator, date, and content URLs are fixed. Immutable historical batches are never
silently edited; any sanitation creates an append-only successor and receipt.

Claims route through an Evidence Index that records population, estimand, hashes,
verifier, and non-implications. Reconstruction certificates do not count again as
independent evidence. Earlier conclusions invalidated by run leakage, common-support
mismatch, or post-execution framing remain in a withdrawal ledger. This governance is
part of reproducibility, not evidence that every retained claim will transport.

# Conclusion

A useful critic for ML-engineering search must be cheaper than execution, but a
credible benchmark must also say which choices, runs, tasks, and information states its
score represents. Decision Corpus provides provenance-bound sibling fragments, a
cost-aware common-support predictor suite, and an executable audit trail for that
measurement problem. Its historical build shows that run isolation, label
repeatability, opportunity-yield weighting, and redundant comparison graphs change
what a predictor number means even when they do not change model ordering. The sealed
temporal cohort is designed to test transport without repeated outcome access. The
resource is therefore a benchmark for predictors and, equally, for the claims made
about them.
