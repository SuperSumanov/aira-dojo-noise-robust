# Decision Corpus: NeurIPS E&D nine-page content budget (2026-09-02)

> Status: `PROVISIONAL_2026_TEMPLATE_BASELINE_NOT_SUBMISSION_CANDIDATE`.
> The 2027 call and style do not yet exist. This document uses the latest official
> 2026 E&D template only to turn page pressure into a measurable editorial constraint.

## Measured baseline, not a word-count guess

The current v0.7 Markdown manuscript was rendered with the official 2026
`neurips_2026.sty` in `eandd` submission mode. The official template ZIP is 20,259
bytes with SHA-256 `82473931e3ef710fcd3f4a8cd4119b9de32e56825f90f9e5a6d55f2d01b817d9`.
The renderer was Tectonic 0.16.9 from its official release, with the Windows asset
digest independently matched to
`131a24604785a9600989a3d91225f597df52ac06f00aeffe86fd529f99ee5cdd`.

The frozen input is 6,476 words, SHA-256
`81d24f04c89c2f780d9b1664996dd2572f4bc6bd7e2d1956e2a52283dc92d925`.
The baseline PDF is 508,714 bytes, SHA-256
`d600c9313e256ccfd4e4274237ee82ef2750186a6769296d339ae6b79846e760`.
It has 17 total pages. Main content still appears on page 16; references begin on
page 16. Therefore this is a 16-content-page upper-bound baseline, not a submission
candidate and not “about two pages over.”

The baseline deliberately preserved the current Markdown structure to diagnose it.
Visual inspection of all 17 rendered pages found five concrete defects:

1. The Markdown H1 repeats the LaTeX title, the internal governance note is visible,
   and “Abstract” is a numbered-text heading instead of an abstract environment.
2. The full related-work matrix consumes roughly two pages and creates overlapping,
   one-word-wide columns. It cannot remain in the main paper.
3. The historical/prospective population tables consume roughly two pages despite
   carrying only a few headline counts.
4. The full audit matrix consumes roughly two pages; its narrow columns are readable
   only at high zoom and are not a defensible use of main-text space.
5. Internal evidence routing appears before the references, and resource paths leak
   into prose/captions. The provisional render also has no completed checklist.

## Nine-page allocation

The next internal candidate is capped at 3,980 prose words and the following exact
page allocation. The 9.0-page sum is a budget, not permission to alter the official
style, font, margins, or line spacing.

| Main-text block | Pages | Prose words | Required visual/table content |
|---|---:|---:|---|
| Abstract + introduction | 1.4 | 780 | Four scoped contributions; no empty sealed numerical promise |
| Related work | 0.6 | 350 | Four nearest competitors in prose; full matrix moves to appendix |
| Corpus + sealed protocol | 1.8 | 600 | Figure 1 and one compact historical/prospective structural table |
| Predictor + audit methods | 1.7 | 700 | Estimands, exact common support, uncertainty, compact cost table |
| Audit findings | 1.5 | 500 | Opportunity-yield identity, Figure 2, condensed non-claim boundaries |
| Benchmark results | 1.2 | 550 | Historical Table 4A and honest prospective protocol status |
| Limitations + release + conclusion | 0.8 | 500 | Accessibility, partial observability, external validity, release state |
| **Total** | **9.0** | **3,980** | References/appendix/checklist excluded from this page budget |

## What stays in the main paper

- A single-paragraph abstract and a short introduction that motivate execution-free
  choice without claiming end-to-end search utility.
- Figure 1, one compact corpus/prospective structure table, and the exact sealed
  closure boundary.
- Predictor estimands, common support, cluster unit, query/init/execution cost, and
  only the minimum graph-basis explanation needed to interpret Table 4A.
- The opportunity-yield size-bias identity and Figure 2, with the high-leverage run
  and non-robust magnitude disclosed in the caption.
- One condensed audit paragraph/table, Table 4A, and an explicit statement that the
  prospective result is not yet available rather than an empty result placeholder.
- Limitations, release/access status, and a short conclusion.

## What moves to the appendix

- The full related-work/governance matrix; detailed historical and prospective
  population tables; complete graph-basis derivation; and the full audit matrix.
- Per-task, task-deletion, gap, and other secondary robustness tables.
- Reconstruction receipts, the full withdrawal ledger, exact commands, and complete
  evidence routing.

Moving these items does not weaken the audit. The main text must state the estimand,
headline readout, and most important failure boundary; the appendix preserves the
evidence needed to verify them.

## What is removed rather than moved

- Internal draft/governance prose, duplicate title headings, and local filesystem
  paths.
- An empty sealed Table 4B promise. If first-960 does not close, the paper describes
  the frozen protocol and its status without reserving a result-shaped hole.
- Conditional Table 5 language unless clean config-v2 provenance, explicit GPU
  approval, frozen two-seed training, and one-shot evaluation all actually complete.

## Acceptance gate for the next draft

The next draft passes only if an official-style render has at most nine content pages,
no overlapping/clipped table cells, no internal paths or governance notes, a real
abstract environment, and no unresolved result placeholder. A successful compile or
a Markdown word count alone is insufficient. All 2026 assumptions must be revalidated
against the 2027 call and style when they are published.
