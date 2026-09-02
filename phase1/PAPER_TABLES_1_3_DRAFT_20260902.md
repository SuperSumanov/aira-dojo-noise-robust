# Decision Corpus Paper Tables 1--3 — Internal Draft（2026-09-02）

> 本文件把 `PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md` 中已允许写作的前三张主表展开为可粘贴稿。
> 它不读取 prospective outcome/prediction，也不把 schema/reconstruction 重复计成科学发现。正式 LaTeX 前仍需压缩列宽、
> 统一引用键，并由学长核对 related-work 描述。

## Table 1. Positioning against direct MLE data and adjacent search benchmarks

### Panel A. Direct MLE data/resources

| Resource | Primary released unit | Main research objective | Execution-derived supervision | Canonical true-sibling decision unit | Independent predictor benchmark | Physical-run/time-forward isolation | Outcome-blind closure | Boundary relevant to our claim |
|---|---|---|---|---|---|---|---|---|
| [ML-Agent](https://arxiv.org/html/2505.23723v2) | 10,000 linear expert execution trajectories over 9 MLE tasks | SFT + step-wise PPO of the actor | Yes; error/action/success metric-change reward | Not its primary released/evaluated unit | No systematic cross-family critic benchmark reported as its primary contribution | Held-out-task transfer, not our run/component/chronological decision split | Not reported as a primary protocol | Closes “first large execution-grounded MLE trajectories” and actor-learning claims |
| [Frontis-MA1 / OpenMLE](https://arxiv.org/abs/2607.28568) + [SFT traces](https://huggingface.co/datasets/FrontisAI/OpenMLE-SFT-Traces) | 26,259 public traces over 4,891 task names | Train Draft/Improve/Debug/Crossover operators and long-horizon evolution | Yes | Not its primary released/evaluated unit | No predictor-suite measurement study as primary contribution | Actor/search evaluation split, not our fixed decision-corpus estimand | Not reported as a primary protocol | Closes largest/first MLE training-trace and learned-operator claims |
| [mle-traj-v1](https://huggingface.co/datasets/jerryyan/mle-traj-v1) / [v3](https://huggingface.co/datasets/jerryyan/mle-traj-v3) | Human/agent code versions, transitions, canonical branches/forest edges and labels | Behavior/state/action/intent analysis over MLE development | Yes; per-version held-out score | Canonical agent tables linearize 13 MLEvolve runs to 189 branches; gated raw true-sibling recoverability remains **unknown** | No common-pool cross-family critic benchmark reported as primary contribution | Physical-run IDs exist for a small agent subset; no verified equivalent of our full isolation/closure bundle | No verified equivalent | Closes first scored MLE trajectory/graph and simple node-count novelty claims |
| **Decision Corpus (ours)** | Provenance-bound recorded-parent sibling **fragments** over generated programs | Measure execution-free candidate predictors under leakage/cost/weighting audit | External pristine continuous grade; validity partial order kept separate | Yes for retained direct siblings; not claimed complete opportunity sets | Yes: exact-common-support predictor families with init/query/execution accounting | Pair/endpoint/parent/run isolation + chronological sealed cohort | Yes: append-only intake, prediction escrow, one-time closure | Defensible novelty is the combined measurement/audit contract, not first/largest trajectory or first tree RM |

### Panel B. Adjacent methods and benchmark precedents

| Work family | What it already establishes | What we borrow / compare | Claim we must not make |
|---|---|---|---|
| [AgentRM](https://arxiv.org/abs/2502.18407), Step-Level Q-Value Models | Reward/value learning from agent search or process states; best-of-N/beam use | Tree-derived supervision and value-model evaluation boundary | “First reward model from a search tree” |
| [ReLoc](https://arxiv.org/abs/2508.07434) | Parent/sibling local code revisions used to train a revision reward model and guide search | Parent-local comparison as an adjacent estimand | “First sibling/parent reward model for code search” |
| [SELA](https://arxiv.org/abs/2410.17238) and related MCTS-AutoML agents | Tree search over automated ML decisions | Search-tree context and end-to-end baseline | “First tree-search MLE/AutoML agent” |
| [DeltaML-Bench](https://arxiv.org/abs/2608.19653v1) / [BAITBENCH](https://arxiv.org/abs/2608.30724v1) | Real-repository MLE evaluation and planted-shortcut hidden-split integrity auditing | Integrity controls, canonical run evidence, and conservative claim boundaries | “First trustworthy MLE-agent benchmark,” hidden held-out evaluation, or specification-gaming audit |
| NAS predictor benchmarks, including [NAS-Bench-360](https://arxiv.org/abs/2110.05668) | Dataset-first multi-task performance-predictor comparison | Predictor families, tabular benchmark form, init/query accounting | “First performance-predictor benchmark” |
| BenchmarkCards / BetterBench / ReproEval-style reporting | Dataset/benchmark documentation and reproducibility checklists | Machine evidence index, withdrawal ledger, data card | “First benchmark checklist/card” |

**Table 1 caption draft.** Decision Corpus is not positioned as the first or largest MLE trajectory dataset, the first tree-derived
reward model, or the first critic-guided code search method. Its unit and protocol are different: provenance-bound sibling fragments from
fixed agent searches, evaluated as an execution-costly decision benchmark under physical-run/time isolation, outcome-blind closure, and
joint cost/noise/pair-weight auditing. “Not reported” denotes scope after the dated primary-source audits through 2026-09-02, not a proof of absence.

## Table 2. Corpus and benchmark population statistics

### Panel A. Historical v11 release

| Population | Cards / pairs | Parents | Endpoints | Runs | Tasks | Boundary |
|---|---:|---:|---:|---:|---:|---|
| v11 card release | 16,012 cards | — | — | 667 heuristic segments | 25 | 14,339 cards have source-truth provenance; “run” here is the released heuristic segmentation |
| all nine decision resources | 8,107 pairs | — | — | — | — | 7,579 parent-present strict core + 528 lineage-verifiable orphan-parent tier |
| b0 train | 4,263 pairs | 2,293 | 5,499 | 333 | 23 | historical development only |
| b0 frozen | 1,498 pairs | 845 | 2,022 | 92 | 22 | public labeled historical frozen set, not a secret leaderboard test |
| b0 extension | 136 pairs | 114 | 239 | 15 | 10 | later held-run extension; kept separate from frozen |

### Panel B. Sealed prospective structural state at the 2026-09-02 snapshot

| Population | Archives / runs | Endpoints | Pairs | Closure status | Allowed interpretation |
|---|---:|---:|---:|---|---|
| source intake | 296 archives / 559 eligible runs | 14,383 structurally eligible | 3,447 | first-960 remaining 401; closure absent | append-only structural support only |
| latest independently verified fixed-WL prefix | 517 runs | 13,098 scorer-covered | 3,230 | 494→517 added 23 runs, deleted 0 | fixed scorer support; do not substitute for broader 14,383 |
| Target-522 frozen selection/rank | 522/522 reached | withheld | withheld | Stage-A/rank complete; rank=`LIMITED_SUPPORT` | no label, prediction, accuracy, utility, identity or profile disclosed; no post-hoc rescue |
| canonical producer config-v2 | 0 sidecars | — | — | deployment blocker | no exact-stratum clean scaling confirmation yet |

**Table 2 caption draft.** Historical v11 and prospective populations have different provenance and disclosure rules. Historical decision
rows are labeled sibling fragments; prospective values remain sealed. The current 14,383 structural endpoints and the latest independently
verified 13,098-endpoint fixed-scorer prefix are distinct denominators. The table reports physical structural units instead of claiming size
leadership by raw node count.

## Table 3. Audit findings, receipts, and claim boundaries

| Audit axis | Verified readout | What it supports | What it does **not** support |
|---|---|---|---|
| Physical-run split | same-budget train/frozen overlap is 0 in unordered pairs, endpoints, parents and referenced runs | leakage-resistant historical split on four explicit axes | pretraining decontamination or secrecy of public tasks |
| Recorded-parent lineage | 8,107 direct-sibling rows; 7,579 strict parent-present; 528 orphan-parent tier; support gates 35/36 | transparent strict-core vs recoverable-fragment reporting | complete source opportunity sets or semantic/causal parent truth |
| Source provenance | 14,339/16,012 cards (89.5516%) map uniquely to 592 journal SHA; 587/667 heuristic runs covered; 1,673 cards unmapped | quantified provenance coverage and unresolved tail | source-truth coverage for all released cards |
| Label repeatability | 207 usable cards, 10 tasks, 3,017 pair observations; raw agreement 0.965860; task-macro 0.980181 | labels are substantially more stable than chance on the measured subset | universal noise ceiling without symmetry/exchangeability assumptions |
| Deployment cost | static LR/GBM/TF-IDF online pair query p50 is 4,048--6,037× below candidate execution p50 | predictors can be materially cheaper to query than executing programs | improved final score, wall-clock, or search utility |
| Pair-induced weighting | exact pair-share = normalized run-share × opportunity-yield; run→pair task TV=0.337083; yield explains about 0.645/0.595 of HHI/TV increment | run-balanced collection can still yield pair-imbalanced benchmark weights, with explicit leverage bounds | new informative-cluster-size theory, universal causal law, or a deletion-robust magnitude |
| Duplicate scope | no observed cross-run/cross-task duplicates under fixed exact/token/AST normalizations; AST coverage gate not fully passed | no duplicate leakage under the declared detectors and covered subset | no fuzzy/semantic/pretraining duplication |
| Archive gate utility | 14 reject events affect 7 competitions; 6 retain accepted support, 1 links only to zero-checkpoint roots; observed last-usable-support elimination 0 | current structural gate is support-preserving on the settled 283-archive state | future stationarity, causal benefit, or universally lossless filtering |
| Prospective append-only scorer | 494→517 runs is +23/−0 with prior rows byte-preserved | outcome-blind support accrual and scorer continuity | predictor effect before first-960 closure |
| Release schema | 10 resources / 24,119 rows; independent field-path inventory agrees exactly; 27 focused+adjacent tests pass | machine-readable type/nullability/availability boundary | content safety, licensing, or dataset release clearance |
| Conservative content tier | 15,174/16,012 cards content-review-eligible; 838 structure-only under a rule frozen before task/card disposition | conservative isolation retains 94.766425% for later review | “clean” content, legal clearance, or safety of unmatched text |
| Generator provenance axes | configured model ID 16,012/16,012; exact version-or-model 15,905; provider family 9,901 | complete model-ID accounting with provider/contract uncertainty made explicit | serving provider, contract entity, output rights, or release clearance for 6,111 unresolved rows |

**Table 3 caption draft.** Every positive readout is paired with its validity boundary. Audit rows are not assumed statistically
independent, and derived reconstructions/certificates are not counted again as new scientific evidence. Prospective labels, predictions and
utility remain unopened.

## Evidence routing and finalization checklist

| Table | Primary local evidence |
|---|---|
| Table 1 | `实验记录/2026-08-28/MLE直接数据竞品_MLAgent_OpenMLE_mletraj_防撞审计.md`; `RECENT_MLE_INTEGRITY_COMPETITOR_DELTA_20260902.md`; `TWENTY_DAY_POSITIVE_RESULT_SPRINT_20260902.md` |
| Table 2 historical | `results/decision_corpus_audit_v11_20260814/`; `results/v11_source_provenance_audit_20260814/`; data card |
| Table 2 prospective | Evidence Index v10 entries 14/19; `CURRENT_DIRECTION.md` 0L0/0KY |
| Table 3 | Evidence Index v10; Structural Gate Utility Certificate; v11 schema inventory; release-content tier and generator-provenance postflight receipts |

Before camera-ready use: replace inline links with bibliography keys, reconcile terminology with the final English draft, rerun the structural
status receipt, and fill Table 4 only after the one-time closure protocol allows it. Table 5 remains absent unless the clean scaling matrix is
explicitly approved and all C4 gates pass.
