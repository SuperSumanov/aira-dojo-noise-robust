# NeurIPS E&D 2027 provisional submission-readiness gate (2026-09-02)

> The 2027 call has not been published. This gate uses the latest official NeurIPS
> 2026 Evaluations & Datasets (E&D) rules as a provisional template and must be
> revalidated against the 2027 call before submission. It is an internal planning
> artifact, not a claim that 2027 requirements are already known.

## Why the current paper is a strong track fit

NeurIPS renamed the former Datasets & Benchmarks track to Evaluations & Datasets in
2026 and explicitly treats evaluation itself as a scientific object: what is measured,
under which assumptions, and how results are interpreted. The call states that a
submission need not introduce a new model or outperform prior work; datasets,
benchmarks, audits, methodological analyses, protocols, and evaluation tools are in
scope when they materially strengthen meaningful evaluation.

That language is unusually well aligned with Decision Corpus. Our core contribution
is not “another reward model.” It is an estimand- and provenance-aware evaluation of
execution-free predictors under physical-run isolation, incomplete choice
observability, pair-induced task weighting, label repeatability, common support,
cost, and one-shot outcome-blind temporal confirmation.

Official sources:

- 2026 E&D call: <https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets>
- 2026 E&D hosting/RAI guidance: <https://neurips.cc/Conferences/2026/EvaluationsDatasetsHosting>
- 2026 E&D FAQ: <https://neurips.cc/Conferences/2026/EvaluationsDatasetsFAQ>
- 2026 Main Track Handbook: <https://neurips.cc/Conferences/2026/MainTrackHandbook>
- NeurIPS paper checklist: <https://neurips.cc/public/guides/PaperChecklist>

## Hard submission gates under the latest official template

| Gate | Latest official requirement | Current state | Decision |
|---|---|---|---|
| Track fit | Evaluation must be the core intellectual contribution | Main draft now centers estimands, audit protocol, and benchmark interpretation | **PASS** |
| Main-paper format | Default E&D LaTeX style; nine content pages including figures/tables | 6,476-word Markdown draft with two embedded figures; no official LaTeX render | **BLOCKED** |
| Review anonymity | Double-blind by default; linked code/data should be anonymized unless a justified dataset restriction requires single-blind | Current public GitHub repository is identity-bearing; no anonymous mirror/preview receipt | **BLOCKED** |
| Executable artifact | Code is required at submission when a reusable benchmark/evaluation tool is central; it must be documented and executable | Public code exists and is heavily tested, but no anonymous clean-install reviewer bundle exists | **PARTIAL** |
| Dataset access | Datasets/code must be hosted, accessible to all reviewers at submission, and properly documented; non-compliance can justify desk rejection | Content-bearing payload is `PARTIAL / NOT RELEASE CLEARED`; no reviewer-accessible hosted dataset URL | **BLOCKED / DESK-REJECT RISK** |
| Collection compliance | A benchmark collecting new/existing datasets must ensure underlying data comply with hosting/access rules | Competition sources are referenced but redistribution/provider/license scope is unresolved | **BLOCKED** |
| Croissant core | Dataset contribution must include a valid Croissant file | Value-free builder exists, but final URL/license/creator/date/content URLs are intentionally absent | **BLOCKED** |
| Croissant RAI | Minimal RAI fields must cover limitations, biases, sensitive information, use cases, impacts, synthetic data, derivation, generation, and annotation | Data card covers much of this in prose; no final canonical Croissant RAI artifact | **PARTIAL** |
| Paper checklist | Mandatory checklist must accompany the PDF; omission is desk-rejectable | No paper-specific completed checklist yet | **BLOCKED** |
| Results closure | Claims in the abstract/main tables must be supported at submission | Table 4B is sealed; Table 5 is conditional; historical Table 4A is verified | **PARTIAL** |

## Non-negotiable interpretation

Reframing the paper as “analytical” cannot be used to evade accessibility when the
benchmark/data are necessary to inspect the main claims. Conversely, release
clearance does not require publishing competition payloads themselves. A valid
submission package may expose a legally cleared derived artifact—e.g. provenance,
structure, immutable reconstruction manifests, allowed features, split certificates,
and executable evaluation code—while linking to upstream public sources under their
own terms. The exact minimal public tier must be approved by the data/license owners
and must still be sufficient to reproduce every headline result claimed in the paper.

Private first-960 labels may remain sealed for contamination control, but the public
portion must be a real, inspectable contribution. A private holdout is not a substitute
for a missing public benchmark artifact.

## Twenty-day critical path

### D0--D3: freeze the submission artifact boundary

1. Enumerate every byte-level resource required to reproduce Tables 1--4A and Figures
   1--2, and classify it as public-derived, upstream-linked, private holdout, or
   prohibited.
2. Obtain owner decisions for the minimum derived release tier, provider-output scope,
   LICENSE/NOTICE, and five unresolved provider batches. Unknown remains withheld.
3. Decide whether the submission's primary artifact is (a) a released derived dataset
   plus benchmark suite or (b) an evaluation methodology plus executable benchmark.
   The decision must match what reviewers can actually access; it is not rhetorical.

### D2--D7: make a real anonymous reviewer artifact

1. Create an anonymous clean repository or anonymous-git mirror from an exact public
   commit; remove author/host/internal-path metadata and prove installability from a
   fresh environment.
2. Host the approved derived artifact on a supported platform or justified bespoke
   host with a reviewer-accessible preview link.
3. Generate final Croissant core + minimal RAI metadata against the real URL, license,
   creator placeholder appropriate for review, publication date, distributions, and
   RecordSets/FileSets; validate it independently.

### D3--D9: produce the nine-page paper, not another long report

1. Port the v0.7 Markdown manuscript to the official E&D LaTeX template.
2. Keep the contribution table, unit/protocol figure, opportunity-yield figure, one
   historical benchmark table, one cost table, and the sealed/conditional decision.
3. Move evidence routing, detailed audit ledger, per-task results, release tables, and
   proofs to the appendix. Remove internal paths from the main submission.
4. Render and count pages on every material change; nine pages is a hard resource.

### D7--D14: close or remove prospective result slots

1. first-960/Table 4B may be joined exactly once only after closure. If it cannot close
   in time, the paper must not contain an empty main-text result promise; move the
   protocol to future work or an appendix preregistration.
2. Clean 0.6B/4B/8B scaling enters only if real config-v2 sidecars, exact-stratum
   support, a user-approved GPU budget, and the frozen two-seed gate all pass. Otherwise
   remove Table 5 from the main paper rather than substituting exploratory results.

### D10--D17: reproducibility and responsible-release dry run

1. Run the anonymous artifact from a fresh machine/account with no internal data roots.
2. Regenerate every public table/figure and compare hashes or declared numerical
   tolerances.
3. Complete the NeurIPS paper checklist with section references, exact commands,
   uncertainty definitions, compute reporting, licenses, and negative societal impacts.

### D17--D20: adversarial internal review

Ask three reviewers to independently attack: (i) novelty versus FOREAGENT/RPM/AgentRM/
ReLoc and recent MLE integrity benchmarks; (ii) estimand/dependence/statistics; and
(iii) data accessibility/licensing/anonymity. A blocking issue must either be fixed or
explicitly narrow the claim before the internal submission candidate is tagged.

## Day-20 success criterion

Day 20 succeeds only if there is a rendered, nine-page, internally reviewable E&D
paper plus a concrete anonymous artifact/release decision. Additional CPU audits do
not substitute for those deliverables. Clean scaling and one-shot temporal results
raise the ceiling, but their absence must not prevent a complete honest evaluation
paper from existing.
