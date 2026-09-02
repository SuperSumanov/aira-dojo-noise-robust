# Graph-basis sensitivity for pairwise predictor benchmarks

> Submission-facing method note, 2026-09-02. This note formalizes an already frozen
> evaluation view. It adds no result, does not rerun or reselect a model, and does not
> claim new effective-resistance or spanning-tree mathematics.

## Motivation

Pairwise benchmark rows are edges, not independent experimental units. Within a
recorded decision parent, a graph with many cycle edges can contribute many more rows
than a sparse graph spanning the same endpoints. A row mean is still a valid answer
for the realized-row population, but its total mass tracks the pair-construction
process. Decision Corpus therefore reports a second, graph-basis sensitivity rather
than silently treating every cycle row as a fresh unit of information.

## Definition

Let one parent-local comparison component be a simple unweighted graph
\(G=(V,E)\). Duplicate unordered edges are rejected before this calculation. For edge
\(e\), let \(b_e\) be its signed incidence vector, \(L\) the graph Laplacian, and
\(L^+\) its Moore--Penrose pseudoinverse. Define

\[
\pi_e=b_e^\top L^+ b_e.
\]

The standard transfer-current identity identifies \(\pi_e\) with the inclusion
probability of \(e\) under a uniform spanning tree. Foster's identity gives

\[
\sum_{e\in E}\pi_e=|V|-1.
\]

If \(z_e\in[0,1]\) is predictor credit, including half credit for a declared tie,
the component score is

\[
A_{\mathrm{UST}}(G)=\frac{\sum_e \pi_e z_e}{|V|-1}.
\]

For a parent graph with \(C\) connected components, the denominator is its incidence
rank \(|V|-C\), equivalently drawing one independent uniform spanning tree per
component. The benchmark then averages component-weighted edge credit within parent,
parents uniformly within task, and tasks uniformly. The uniform-row reference uses
the identical parent-then-task hierarchy and changes only the within-parent edge
weights.

## Expectation identity

For a uniform spanning tree \(T\), linearity of expectation yields

\[
\begin{aligned}
\mathbb{E}_T\left[\frac{1}{|V|-1}\sum_{e\in T}z_e\right]
&=\frac{1}{|V|-1}\sum_{e\in E}\Pr(e\in T)z_e\\
&=\frac{1}{|V|-1}\sum_{e\in E}\pi_e z_e.
\end{aligned}
\]

Thus the statistic is expected predictor credit on a uniformly sampled spanning
basis. A bridge has \(\pi_e=1\). In a complete graph on \(k\) endpoints, every edge
has \(\pi_e=2/k\), so the UST and uniform-row means agree within that component. The
views differ only when observed parent graphs have nonuniform graph leverage.

## What this method does and does not do

It does:

- cap each component's total edge mass at its incidence rank rather than its raw row
  count;
- expose how incomplete or cyclic comparison geometry changes benchmark weighting;
- preserve all observed edges while giving an exact expected-basis interpretation;
- provide a paired sensitivity using the same support and aggregation hierarchy.

It does not:

- turn dependent edge outcomes into independent samples;
- estimate an effective sample size or justify pair-i.i.d. confidence intervals;
- remove adaptive-search, missing-choice, task-selection, label-noise, or
  pretraining-contamination bias;
- make the statistic invariant to adding a different observed edge;
- replace the realized-row estimand as the uniquely correct headline;
- constitute new effective-resistance, Foster, Kirchhoff, or spanning-tree theory.

Task-clustered intervals and leave-one-task-out views therefore remain mandatory.
Uniform-row and UST estimates are reported side by side; neither may be selected after
observing which favors a model.

## Bound evidence and current readout

The paper's historical Table 4A binds this method to the frozen 931-row
exact-common-support development graph. That graph has incidence rank 787 and 144
cycle rows. Producer and non-importing verifier agree on weights, graph accounting,
aggregates, and ranking reconstruction. On this support the weighting is structurally
nontrivial, but the preregistered nested task--parent headline and predictor ordering
do not materially change. This is a useful robustness result, not a predictor gain.

Authoritative artifacts:

- `historical_ust_predictor_sensitivity_v2.json`;
- `historical_ust_predictor_sensitivity_formal_receipt_20260830.json`;
- `analyze_historical_ust_predictor_sensitivity.py`;
- `verify_historical_ust_predictor_sensitivity.py`;
- `HISTORICAL_TABLE4A_EVIDENCE_DECISION_20260902.md`.

`counts_as_distinct_claim_evidence=false`: this note formalizes and routes the
existing evidence; it does not create another experimental observation.
