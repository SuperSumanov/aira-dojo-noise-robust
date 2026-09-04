# Decision Corpus related-work / scoop map (2026-09-02)

> Scope: primary-source citation and claim-boundary map for the current manuscript.
> This file records no new experimental result and does not authorize reading sealed
> outcomes, fitting a model, or running an API/GPU job. `CURRENT_DIRECTION.md` remains
> the scientific authority.

## Immediate positioning decision

Two papers directly establish the practical premise of pre-execution preference for
ML-agent candidates:

1. **FOREAGENT / Can We Predict Before Executing Machine Learning Agents?**
   ([arXiv:2601.05930v2](https://arxiv.org/abs/2601.05930)) defines Data-centric
   Solution Preference, reports a 26-task / 895-solution / 18,438-comparison corpus,
   and integrates pairwise prediction into a Predict-then-Verify agent.
2. **AI Research Preference Models (RPM)**
   ([arXiv:2608.13940v2](https://arxiv.org/abs/2608.13940)) generates 15 unexecuted
   children from one parent inside AIRA-dojo and uses an inference-only or agentic
   preference model to choose one for execution. Its main evidence is a positive
   20-task, 10-seed end-to-end study; its separate offline study uses 1,000 sibling
   pairs, drops normalized-test-gap near-ties below 0.01, and labels a node by the
   best test score in its observed subtree.

These papers close the following claims for Decision Corpus:

- first pre-execution comparison of two ML-agent solutions;
- first ML-solution preference corpus;
- first preference-guided child selection in AIRA-dojo;
- first evidence that candidate preference can improve ML-agent score or time to a
  fixed score;
- novelty based only on subtree-best labels, larger judges, longer context, prompt
  optimization, ensembling, or pilot experiments.

The defensible Decision Corpus claim is narrower and complementary: a reusable,
audit-grade benchmark for naturally logged MLE search decisions, with explicit
physical-run/config/time isolation, incomplete-fragment accounting,
failure/unknown preservation, candidate/parent/run/task dependence, label
repeatability, initialization/query/execution cost, pair-graph weighting, and an
outcome-blind temporal closure. RPM is the strongest method baseline/motivation;
FOREAGENT is the strongest released preference-corpus baseline. Neither should be
described as merely adjacent work.

## Direct comparison matrix

| Axis | FOREAGENT | RPM | Decision Corpus |
|---|---|---|---|
| Main unit | Within-task combinations derived from a curated solution pool | Online contemporaneous 15-child batches; separate 1,000-pair offline sibling set | Provenance-bound recorded-parent sibling fragments from naturally logged searches |
| Main label | Better executed solution | Online selected candidate utility; offline observed-subtree maximum test score | Immediate pristine execution result and separately certified validity/unknown relations |
| Candidate reuse / dependence | One solution appears in many derived pairs | Offline pairs inherit greedy/off-policy subtree opportunity; online batches are the practical evidence | Endpoint, parent, physical run, task, component, and time identities are explicit audit axes |
| Failures / near-ties | Invalid submissions and near-ties are filtered in corpus construction | Offline gap below 0.01 is filtered | Failure/unknown and repeat-grade uncertainty are retained and reported separately |
| Evaluation role | LLM preference feasibility plus 5-task agent integration | Strong end-to-end child-selection method study | Cross-family predictor measurement, transport, cost, and benchmark-governance study |
| What it proves for us | The problem is real and a strong LLM can carry signal | Candidate selection can improve end-to-end AIRA-dojo search | Whether predictor numbers remain interpretable under stricter units, dependencies, and prospective closure |

The comparison must not be used to diminish the competitors' positive results. In
particular, RPM's end-to-end experiment is stronger practical-utility evidence than
an offline archival benchmark. Conversely, an online positive result does not by
itself answer the release, leakage, weighting, noise, and transport questions that
Decision Corpus is designed to measure.

## 2026-09-05 direct trajectory-system addendum: TOFFEE

**TOFFEE** ([arXiv:2607.06233v3](https://arxiv.org/abs/2607.06233),
[official artifact](https://github.com/wang0702/toffee)) is a direct neighbor that
must be cited, not hidden under generic data-agent work. It is a VLDB 2026 demo with
execution-grounded MCTS, cross-task prefix reuse, a learned contextual-bandit cost
model, and a released 30K trajectory corpus for SFT/ICL. It closes broad claims for
the first MCTS data-agent trajectory corpus, first large public data-agent trajectory
release, first adaptive model/context/branching controller, and first cross-task
prefix reuse.

The artifact card describes each released sample as one full multi-turn trajectory.
It does not state that the release includes rejected sibling alternatives or complete
search-time choice sets. Record those fields as `unknown/not stated`, not `absent`;
the paper's internal system may retain information that the public trajectory format
does not expose. Decision Corpus should be contrasted on the released evaluation
unit: naturally logged alternative-bearing MLE code decisions, not SFT trajectories.

Add the following columns to the manuscript's resource comparison table and require
an artifact citation for every non-unknown cell: released unit; alternative candidates;
choice-set identity; physical-run identity; external continuous score; failure/unknown
retention; repeat grading; endpoint/pair dependence; init/query/execution cost split;
and outcome-blind temporal escrow. This is a schema comparison, not a claim that more
columns imply a better agent system.

**Discriminative World Models for Web Agents**
([arXiv:2609.02885v1](https://arxiv.org/abs/2609.02885)) is an even newer direct
boundary. Its abstract explicitly describes a branching WebArena Go-Browse dataset
where every decision point has multiple alternative actions and resulting states,
then reports gains on held-out predicted-state matching, PRM-style action ranking,
and end-to-end WebArena-Lite selection. It closes generic priority claims for an
alternative-bearing agent decision dataset and for learning a selector from branch
outcomes. Decision Corpus must be positioned as an MLE-program domain measurement
resource with external continuous grading, physical-run isolation, cost/noise/
missingness/dependence audit, and temporal escrow—not as the first branching corpus.
This comparison is limited to the public v1 materials inspected on 2026-09-05.

## Required manuscript citations

### Direct competitors

- Jingsheng Zheng et al., **Can We Predict Before Executing Machine Learning
  Agents?**, arXiv:2601.05930v2 / ACL 2026.
- Thomas Simon Foster et al., **AI Research Preference Models**,
  arXiv:2608.13940v2.

### MLE trajectories and actor/operator learning

- Ziting Wang et al., **Demonstrating TOFFEE: A Learned System for Synthesizing
  Data Agent Trajectories at Scale**, [arXiv:2607.06233v3](https://arxiv.org/abs/2607.06233),
  VLDB 2026 demo; cite the official TOFFEE-30K artifact separately.
- Zexi Liu et al., **ML-Agent: Reinforcing LLM Agents for Autonomous Machine
  Learning Engineering**, [arXiv:2505.23723](https://arxiv.org/abs/2505.23723).
- Junlin Yang et al., **Frontis-MA1: Training an AI4AI Model towards Recursive
  Self-Improvement in Machine Learning Engineering**,
  [arXiv:2607.28568](https://arxiv.org/abs/2607.28568).
- `mle-traj`: cite the exact v1/v3 Hugging Face artifacts used by the 2026-08-28
  audit at revisions `4fc7f6e3...f3285` / `97b1217a...161d3`; do not infer
  raw-tree recoverability beyond those inspected objects. The v1 card's proposed
  proceedings BibTeX has a literal author placeholder, so it is not a paper citation.

### Reward/value-guided search

- Kelvin Li et al., **Discriminative World Models for Web Agents**,
  [arXiv:2609.02885v1](https://arxiv.org/abs/2609.02885).
- Yu Xia et al., **AgentRM: Enhancing Agent Generalization with Reward Modeling**,
  [arXiv:2502.18407](https://arxiv.org/abs/2502.18407).
- Yuanzhao Zhai et al., **Enhancing Decision-Making for LLM Agents via Step-Level
  Q-Value Models**, [arXiv:2409.09345](https://arxiv.org/abs/2409.09345).
- Zhiyi Lyu et al., **Let's Revise Step-by-Step: A Unified Local Search Framework
  for Code Generation with LLMs**, [arXiv:2508.07434](https://arxiv.org/abs/2508.07434).
- Yizhou Chi et al., **SELA: Tree-Search Enhanced LLM Agents for Automated Machine
  Learning**, [arXiv:2410.17238](https://arxiv.org/abs/2410.17238).

### Predictor-benchmark precedent

- Colin White et al., **How Powerful are Performance Predictors in Neural
  Architecture Search?**, [arXiv:2104.01177](https://arxiv.org/abs/2104.01177).
- Arjun Krishnakumar et al., **NAS-Bench-Suite-Zero: Accelerating Research on
  Zero Cost Proxies**, [arXiv:2210.03230](https://arxiv.org/abs/2210.03230).
- Renbo Tu et al., **NAS-Bench-360: Benchmarking Diverse Tasks for Neural
  Architecture Search**, [arXiv:2110.05668](https://arxiv.org/abs/2110.05668).

### Estimand and informative-cluster-size precedent

- John M. Williamson, Somnath Datta, and Glen A. Satten, **Marginal Analyses of
  Clustered Data When Cluster Size Is Informative**, *Biometrics* 59(1):36--42,
  [doi:10.1111/1541-0420.00005](https://doi.org/10.1111/1541-0420.00005).
- Brennan C. Kahan, Fan Li, Andrew J. Copas, and Michael O. Harhay, **Estimands in
  Cluster-Randomized Trials: Choosing Analyses That Answer the Right Question**,
  *International Journal of Epidemiology* 52(1):107--118,
  [doi:10.1093/ije/dyac131](https://doi.org/10.1093/ije/dyac131).

These works establish that unit-weighted and cluster-weighted analyses can target
different quantities when cluster size is informative. Decision Corpus therefore
does not claim novelty for size-biased weighting, inverse-size weighting, macro/micro
averaging, or the associated algebra. Its scoped contribution is the outcome-blind,
machine-frozen mapping from MLE-agent run composition through structural sibling
opportunity yield and evaluability into the predictor benchmark's task mixture,
including a fail-closed rule for zero-support tasks.

### Benchmark governance

- **BenchmarkCards**, [arXiv:2410.12974](https://arxiv.org/abs/2410.12974).
- **BetterBench**, [arXiv:2411.12990](https://arxiv.org/abs/2411.12990).
- **Establishing Best Practices for Building Rigorous Agentic Benchmarks**,
  [arXiv:2507.02825](https://arxiv.org/abs/2507.02825).
- **ReproEvalCard**, ACL 2026, must be cited from its ACL Anthology record rather
  than a secondary summary when the bibliography is finalized.
- **DeltaML-Bench**, [arXiv:2608.19653v1](https://arxiv.org/abs/2608.19653v1),
  is a direct real-repository MLE benchmark and specification-gaming precedent.
- **BAITBENCH**, [arXiv:2608.30724v1](https://arxiv.org/abs/2608.30724v1), is a
  direct hidden-robust-split and reward-hacking audit precedent for ML agents.

The last two papers close broad priority language around trustworthy MLE-agent
benchmarks, hidden held-out evaluation, and integrity auditing. They do not change
the current narrow unit: naturally logged sibling fragments evaluated as a
cross-family predictor benchmark under physical-run/config/time isolation and
outcome-blind closure. This statement is scoped to the inspected public v1 papers,
not an assertion about all literature or unobserved internal work.

## Table 4B baseline consequence

The one-shot prospective table should contain an explicitly named
**RPM-style inference-only transfer baseline** in the LLM-judge family, or state
plainly why it could not be run. This is not a reproduction claim unless the exact
public prompt, model, context construction, tournament, and inference budget are
matched. Before closure, only prompt/source/model/budget metadata may be frozen;
no label, outcome, prediction value, accuracy, or utility may be read.

The source binding is now explicit rather than aspirational. The latest v2 TeX
source is 458,133 bytes with SHA-256
`9910b62a9b8c9bb7da864fbb8534b124e697cf397a04103b43a273329e050ca0`;
`sections/appendices/inference_only.tex` is 18,814 bytes with SHA-256
`f44585395980052a631d8eef19424759d22aebd3b3745fbfbd84d57b983a8c72`.
Its optimized-prompt block is checked in byte-exact at
`phase1/baselines/rpm_inference_only_optimized_v2.txt` (1,950 bytes, SHA-256
`d64763172087a4243ddfa3ff364fad071c552af0783e5786a301a37bc338ff96`).
The accompanying contract and network-free renderer do not authorize a model call.
A supplemental context contract now fixes the same-run/task, strictly pre-candidate
selection rule and permits only then-visible self-reported validation, never the
post-hoc external grade. Exact tokenizer-based node packing, model, cost, content
clearance, and the outcome-blind panel remain separate pre-run gates.

Minimum result-time reporting for this row:

- exact RPM paper/source version and prompt hash;
- model/checkpoint/provider and context-node construction;
- pair ordering and position-bias handling;
- initialization, per-pair query latency, token/compute cost, coverage, and parse
  failure rate;
- the same common-support, task/run clustering, and no-rescue rules as every other
  Table 4B predictor.

If the exact Qwen3.6-27B setup is unavailable, a model-matched prompt transfer may
be reported under a different name. It must not be labeled “RPM reproduction.”

## Source chronology and evidence boundary

- FOREAGENT and RPM were already identified and routed in
  `CURRENT_DIRECTION.md` sections 0DN/0DO on 2026-08-22. This 2026-09-02 file is a
  manuscript/citation consolidation, not a newly discovered scientific result.
- RPM v2 (2026-08-25) was checked against the primary arXiv HTML. It retains the
  end-to-end child-selection result, explicitly acknowledges off-policy/subtree-max
  bias in the offline set, reports inference latency, and leaves parent selection
  to future work. Those boundaries do not authorize reviving our closed parent or
  lookahead lines.
- Claims about what another paper “does not report” are scoped to the inspected
  public paper/release version; they are never claims about unobserved internal work.

## Working bibliography state

`DECISION_CORPUS_REFERENCES_20260902.bib` now binds 26 primary-source-checked entries
used by this map and the manuscript. Large author lists that use BibTeX's canonical
`and others` marker are explicitly internal-draft abbreviations and must be expanded
from the linked primary record during final venue packaging. mle-traj v1/v3 artifact
identity is now revision-pinned, while the formal proceedings authorship remains
unresolved because the card itself supplies `<AUTHOR_NAME> et al.`; no paper citation
may be invented from the repository account.
