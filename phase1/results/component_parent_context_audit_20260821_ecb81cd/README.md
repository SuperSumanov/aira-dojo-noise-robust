# Component parent-context audit

Formal status: `VERIFIED_PARENT_CONTEXT_OVERLAP_CONFINED_TO_SYNTHETIC_DRAFT`.

This compact tracked bundle records the outcome-blind structural audit executed from commit
`ecb81cdf730961bd01799faeeb0bd60281537984`. The producer was run twice and an implementation that
does not import it independently rebuilt the result twice. All four outputs were byte-identical within
implementation, all fields matched across implementations, and the five focused synthetic tests passed.

The sealed full bundle is
`/research/d7/spc/yzyang4/component-parent-context-audit/ecb81cd-v1`. Its 31-entry manifest has SHA-256
`48489935f14dcec34829cae92f23cc0b144513ac41bc69a119e958471e6c2bd5`; every manifest entry was
rechecked successfully, all four reproducibility diffs and all stderr files are empty, credential-shape
scans report zero hits, and no sealed file is writable.

The fixed component split has zero outer-train/test endpoint-run overlap, but 80 shared `(task,parent)`
contexts affecting 305 test rows. All 305 rows are synthetic Draft; Improve has zero shared parents.
Endpoint exact-code overlap is zero. This verifies a pair-construction/split-unit failure mode, not a causal
explanation of model accuracy and not leakage in canonical Improve/raw-sibling evaluation.

`summary.json` intentionally retains the producer's pending status because a producer cannot authorize its
own claim. `final_verification_receipt.json` and `combined_conclusion.json` are the independent authorization.
