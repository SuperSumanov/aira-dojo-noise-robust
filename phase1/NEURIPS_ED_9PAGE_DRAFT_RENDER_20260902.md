# Decision Corpus: measured nine-page draft render (2026-09-02)

> Status: `VISUALLY_VERIFIED_INTERNAL_CANDIDATE_PROVISIONAL_2026_TEMPLATE`.
> This closes the measured page-budget gate, not the submission-readiness gate.

## Result

The condensed manuscript at
`phase1/PAPER_DRAFT_DECISION_CORPUS_9PAGE_20260902.md` was rendered with Pandoc 3.6,
Tectonic 0.16.9, and the latest official NeurIPS 2026 E&D style as a provisional gate
for the unpublished 2027 call. The source has 2,903 whitespace-delimited words. Its
PDF has eight total pages; main content ends on page 7 and the references begin on
page 7. The draft is therefore inside the nine-content-page limit without changing
the official font, margins, line spacing, or style.

Relative to the measured v0.7 baseline, the source is 3,573 words shorter and the
last main-content page moves from 16 to 7. This is an editorial compression result,
not a predictor or search result. It does not count as distinct scientific evidence.

## Visual QA

All eight final pages were rendered to PNG and inspected as a contact sheet. Pages
1, 3, 4, 6, 7, and 8 also received high-resolution checks across the two render
passes. No clipping, overlap, duplicate title, internal governance note, internal
filesystem path, or unresolved result placeholder was observed. The final pass has
an explicit References heading, zero overfull-box warnings, and three nonfatal
underfull-vbox warnings. The two figures and the compact corpus, historical-result,
and cost tables remain readable at full-page resolution.

## Reproducible render boundary

The source, bibliography, two figures, official template ZIP and style, Tectonic
asset, and the tracked E&D header are SHA-256 bound in
`phase1/decision_corpus_9page_draft_render_v1.json`. Pandoc must use
`markdown+tex_math_single_backslash`, standalone mode, citeproc, the frozen
bibliography, and the tracked header. Tectonic must be able to resolve the unpacked
official `neurips_2026.sty` and `phase1/figures`, and must run in deterministic mode.
Two independent build directories then produced byte-identical 467,024-byte PDFs with
SHA-256 `61d306c76ce0d6d57cc44547a320266a1853cc678b938adb7a7c23f7b1968df5`.
The generated PDF is a local review artifact and is not committed to Git.

## What remains blocked

This is not yet a submission candidate. The 2027 call and style must be revalidated
when published; the official checklist is not included; the anonymous reviewer
artifact, dataset access and release clearance, and core Croissant metadata remain
blocked; and the prospective result remains sealed until its preregistered closure.
The spare page capacity is revision headroom, not permission to pad the paper or add
an unsupported positive claim.

No prospective label, outcome, prediction value, accuracy, utility, candidate
identity, profile, or raw archive payload was read. GPU jobs, paid API calls, model
fits, and base-model updates were all zero.
