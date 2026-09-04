# G-reuse to Local: related-work boundary and next falsifiable method candidate

Date: 2026-09-05. This is a result-blind method boundary and experiment proposal, not a
model-effect result or an authorization to train. It does not modify frozen v2, historical
development v1, G0 job 12377, protected cohorts, or the existing five-arm decision.

## What cannot be claimed as novelty

The broad ideas are established:

- Rank Centrality connects pairwise-estimation error and the comparison graph's spectral
  gap ([Negahban, Oh, and Shah, NeurIPS 2012](https://proceedings.neurips.cc/paper/2012/hash/815104ed949be8efaea77bced01fd5d0-Abstract.html)).
- Local grouping followed by MLE is already used in full ranking from pairwise comparisons
  ([Chen et al., 2022](https://arxiv.org/abs/2101.08421)).
- Weak-supervision pretraining followed by ranking adaptation is already represented by
  [AceNAS](https://arxiv.org/abs/2108.03001), and pairwise ranking losses for NAS predictors
  are extensively studied by
  [PWLNAS](https://openaccess.thecvf.com/content/ICCV2025/html/Ji_Loss_Functions_for_Predictor-based_Neural_Architecture_Search_ICCV_2025_paper.html).
- Cross-space and multi-task transfer for performance predictors is already studied by
  [Multi-Predict](https://proceedings.mlr.press/v224/akhauri23a.html); performance predictors
  with fit/query-cost accounting are represented by
  [EmProx](https://proceedings.mlr.press/v191/franken22a.html).
- Pointwise and pairwise objectives in one model, followed by pointwise initialization and
  pairwise local refinement, already appear in
  [Efficient Pointwise-Pairwise Learning-to-Rank for News Recommendation](https://aclanthology.org/2024.findings-emnlp.723/).
- D-optimal pairwise data collection and graph connectivity are established by
  [Osting et al., JMLR 2014](https://www.jmlr.org/papers/v15/osting14a.html), while
  [Shah et al., JMLR 2016](https://www.jmlr.org/papers/v17/15-189.html) gives topology-dependent
  minimax bounds for BTL/Thurstone estimation.
- [Guo et al., SDM 2019](https://ece.northeastern.edu/fac-ece/ioannidis/static/pdf/2019/C_Guo_Accelerated_SDM_Submit_2019.pdf)
  already studies accelerated D-optimal greedy selection for pairwise comparisons, and
  [Mikhailiuk et al., 2020](https://arxiv.org/abs/2004.05691) combines information-gain
  selection with a minimum spanning tree construction.
- The closest newly found label-reuse analogue is
  [Chowdhury and Esfahani, RecSys 2026](https://arxiv.org/abs/2608.18531): every candidate
  in a fixed offline explanation pool already has a scalar BERTScore label, and a five-seed
  LambdaRank system exploits all candidate labels better than several single-action RL
  formulations. This directly precludes a broad novelty claim that converting an already
  labelled candidate pool into dense ranking supervision is new.
- [Cao et al., ACL Findings 2026](https://aclanthology.org/2026.findings-acl.1638/) convert
  scalar mean-opinion scores into a preference benchmark, stratify by score gap, and add a
  gap-aware reward for difficult pairs. This precludes novelty claims for scalar-score to
  pair conversion or gap-stratified reward-model diagnosis in general.
- [Fathullah and Gales, UAI 2025](https://proceedings.mlr.press/v286/fathullah25a.html)
  combine absolute and comparative scoring and report more efficient comparison selection.
  Thus even a future P-to-L result cannot be sold as the first absolute/comparative hybrid.
- [Zhai et al., AAAI 2025](https://doi.org/10.1609/AAAI.V39I25.34924) construct preferences
  from MCTS-derived step-level Q values and use the learned value model to guide an agent's
  next action. It is a direct step-value precedent, though not an MLE experiment corpus with
  execution-cost, physical-run provenance, and prospective audit controls.

Therefore this project must not claim first global-to-local training, first pointwise-to-
pairwise adaptation, first use of a comparison graph, first D-optimal/effective-resistance
pair selector, first information-gain spanning-tree batch, first reuse of cached scalar labels
as ranking supervision, first gap-stratified preference diagnosis, or a new generic ranking algorithm.
The paper's novelty remains the Decision Corpus, cost/provenance accounting, and the audit
protocol. A successful G-reuse experiment is a mechanism result inside that paper.

## What remains defensible after the direct-overlap check

No inspected paper combines the following package: full-program MLE-agent search trees;
external execution grades whose generation cost is separated from predictor initialization
and query cost; physical-run-clean local sibling decisions; the same execution-record
population reorganized into global and local constraints under a fixed training-token budget;
and a prospective append-only, outcome-blind audit with leakage retractions and one-shot
frozen evaluation. This is an inference from the cited works, not proof that no unpublished
or unindexed work exists.

Consequently the safest positive paper claim is not a new ranking primitive. It is a dataset
and controlled empirical finding: whether supervision geometry extracted from already-paid
MLE executions changes decision quality and training cost once execution population, token
budget, split provenance, and evaluation access are held fixed. The five-arm hash/G-only/
local-repeat controls and the prospective audit are what distinguish that finding from the
closest RecSys and speech-score precedents.

The post-0L21 selector is consequently fixed as an **existing-theory cost challenger**, not
the headline method. The only model-stage cost point is 50% because it was frozen before the
25/50/75 frontier was observed; the better-looking 75% point may not be selected post hoc.
The exact stage ordering and non-inferiority boundary are recorded in
`G_REUSE_EFFECT_TRANSLATION_DECISION_20260905.md`.

## Current candidate and estimand

The current G-reuse to L candidate asks a narrower question: with the same already executed
MLE programs and the same external score records, can one derive additional within-task,
exact-stratum global relations and use them before local-sibling adaptation to improve
run-clean local decisions at a fixed training-token budget?

This is an execution-label-efficiency estimand. Derived pair rows are correlated constraints,
not independent labels. Same endpoint identity alone is insufficient: an authoritative,
same-version source package must bind every endpoint to the same execution and evaluator
record, and the experiment split must be closed before fitting.

## Stronger alternative worth screening: pointwise-score to local preference

Pairwise G-reuse throws away scalar information by converting every endpoint score into
directions. A plausible stronger arm is pointwise external-score pretraining followed by the
same local Bradley-Terry adaptation. Call it P-to-L. It is not a novelty claim; it tests
whether the corpus's continuous pristine score is a more label-efficient pretraining target.

The prior evidence does not justify replacing G-reuse with P-to-L. PWLNAS reports that ranking
losses can lead in low-data and local-mutation settings, while weighted/regression objectives
can help with more data or top-of-list discrimination; the preferred loss is task- and regime-
dependent. The current action is therefore a one-pivot challenger under the same budget, not
a loss sweep and not an assumption that retaining scalar magnitude must improve decisions.

P-to-L is not added to the frozen five arms now. It may enter a later, separately approved
historical-development screen only if the authoritative same-version package supports all of:

1. score direction, units, missingness and ties are explicit and immutable;
2. pairs and endpoints are restricted to the same task and exact producer/config stratum;
3. normalization parameters are learned only from train physical runs, then frozen;
4. source execution identity, endpoint identity and evaluator identity are closed;
5. train/dev/frozen access is enforced before any target-value inspection or fit;
6. P-to-L and G-reuse-to-L share endpoint eligibility, initialization, tokenizer, valid-token
   cap, optimizer, LR-by-consumed-token rule and local-adaptation stream;
7. endpoint repetitions and derived pair multiplicities are logged rather than treated as
   independent sample size.

## Minimal fair screen after the source gate opens

Use the existing pivot model and seeds 6/7/8; do not sweep model size or losses. Primary
comparison remains G-reuse-to-L versus Lbudget. P-to-L is a challenger, not a replacement,
and gets the same total valid-token cap. Retain L1, Gbudget and the existing fixed-target
negative control needed by the frozen protocol. Selection uses train-run dev only; all
checkpoints are locked before any untouched evaluation population is accessed.

Success is not a single higher mean. Keep the existing gate: primary delta at least 0.02,
task-clustered paired 95% confidence lower bound above zero, all three seed directions
positive, leave-one-task-out never reverses, and no task contributes more than 0.35 of the
aggregate gain. Report training tokens, updates, padding, wall time and GPU-hours separately.

The immediate no-fit action is only a source-readiness audit. If score scales are not
comparable within exact strata, or same-execution identity cannot be proved, P-to-L is killed
without training. Any real fit still requires a matrix and total GPU-hour approval.
