# Provisional NeurIPS checklist render gate (2026-09-03)

Status: **VISUALLY VERIFIED, BUT NOT SUBMISSION READY**.

The official 2026 NeurIPS paper checklist is bound by its original SHA-256, then its
tracked copy is normalized to UTF-8/LF with trailing whitespace removed before the
instruction block is removed mechanically. All 16 questions and guideline blocks are
retained. The provisional answers are 7 Yes / 5 No / 4 N/A. The five No answers are
real submission work items, not formatting placeholders: full result reproducibility,
anonymous data/code access, total compute accounting, existing-asset licenses, and new
asset documentation/hosting. Item 9 remains N/A until the authors perform and attest a
Code of Ethics review. The pipeline must not cosmetically convert any of these answers.

The successor manuscript adds a bounded broader-impact/safeguard/LLM-use section and the
successor appendix adds exact historical estimator, inference, and CPU-cost settings.
It does not alter a scientific value or open any sealed prospective field. Visual QA
also found four lone CR bytes in the immutable 2026-09-02 source where
`\rightarrow` was intended. The successor repairs exactly those four hash-bound tokens;
the base source remains unchanged. A regression test now requires four proper arrow
tokens and zero lone CR bytes.

Two independent Pandoc 3.6 + Tectonic 0.16.9 builds, using only cached resources and
deterministic mode, produced byte-identical 500,133-byte PDFs with SHA-256
`a0025a12d60ee4dd7ea2caf8da6ace8451227b1f75a89e90775817d74397a359`.
The PDF has 16 pages: main content ends on page 7, references begin on page 8, and the
checklist starts on a forced fresh page 9 and occupies pages 9--16. Thus the manuscript
remains inside the measured nine-content-page gate. The TeX log has zero overfull-box
warnings, three underfull-vbox warnings, and one underfull-hbox warning.

All 16 final pages were rendered to PNG and inspected. The arrows, two figures, compact
corpus table, predictor table, cost table, references, every checklist answer, and page
transitions are visible. No overlap, clipping, missing figure, or black box was observed.
The PDF is an internal review candidate, not a submission candidate; the 2027 call and
style are not published, and the five checklist blockers plus author attestation and the
sealed closure gate remain open.

Security boundary: prospective label/outcome/prediction/accuracy/utility and candidate
identity/profile reads were all false. GPU, paid API, model fit, and base-model update
counts were **0 / 0 / 0 / 0**. This render closes a submission-engineering presence and
visual gate only; it is not distinct scientific evidence.
