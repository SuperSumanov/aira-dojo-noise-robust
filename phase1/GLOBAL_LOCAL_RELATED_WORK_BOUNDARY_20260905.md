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

Therefore this project must not claim first global-to-local training, first pointwise-to-
pairwise adaptation, first use of a comparison graph, or a new generic ranking algorithm.
The paper's novelty remains the Decision Corpus, cost/provenance accounting, and the audit
protocol. A successful G-reuse experiment is a mechanism result inside that paper.

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
